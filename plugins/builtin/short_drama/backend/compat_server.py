"""Local compatibility API for persisted short-drama projects and media."""

from __future__ import annotations

import json
import base64
import hashlib
import math
import mimetypes
import os
import re
import signal
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import time
import zlib
from contextlib import contextmanager
from datetime import UTC, datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlencode, urlparse
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4

from plugins.builtin.short_drama.workflows.production_ledger import CANONICAL_STAGES, ProductionLedger, ProductionLedgerError, canonical_stage
from plugins.builtin.short_drama.workflows.production_orchestrator import ProductionOrchestrator
from plugins.builtin.short_drama.workflows.story_bible import StoryBible, StoryBibleError
from ai_agent_core import ResourceScheduler, WorkerRegistry, WorkerSnapshot, WorkloadRouter, atomic_write_json
from ai_agent_queue import DurableTaskRepository, TaskLeaseError, TaskLeaseRepository
from ai_agent_adapters import production_capability_registry, production_extension_registry
from plugins.builtin.short_drama.backend.web_search import WEB_SEARCH_PROVIDER_DESCRIPTIONS, search_web


APPLICATION_ROOT = Path(__file__).resolve().parents[4]
OUTPUT_ROOT = Path(os.environ.get("SHORT_DRAMA_OUTPUT_ROOT", str(APPLICATION_ROOT / "output"))).resolve()
PROJECTS_FILE = OUTPUT_ROOT / "narrative-cache" / "projects.json"
PROJECT_SNAPSHOTS_DIR = OUTPUT_ROOT / "narrative-cache" / "project-snapshots"
PROJECT_VERSIONS_DIR = OUTPUT_ROOT / "narrative-cache" / "project-versions"
ASSISTANT_FILE = OUTPUT_ROOT / "narrative-cache" / "assistant-conversations.json"
AGENT_JOBS_FILE = OUTPUT_ROOT / "narrative-cache" / "system-agent-jobs.json"
IMAGE_JOBS_FILE = OUTPUT_ROOT / "narrative-cache" / "character-image-jobs.json"
TEXT_JOBS_FILE = OUTPUT_ROOT / "narrative-cache" / "text-generation-jobs.json"
VIDEO_JOBS_FILE = OUTPUT_ROOT / "narrative-cache" / "video-jobs.json"
PRODUCTION_QUEUE_FILE = OUTPUT_ROOT / "narrative-cache" / "production-queue.json"
RESOURCES_FILE = OUTPUT_ROOT / "narrative-cache" / "resources.json"
PRODUCTION_LEDGER_FILE = OUTPUT_ROOT / "narrative-cache" / "production-ledger.sqlite"
PRODUCTION_ORCHESTRATOR_FILE = OUTPUT_ROOT / "narrative-cache" / "production-orchestrator.sqlite"
STORY_BIBLE_FILE = OUTPUT_ROOT / "narrative-cache" / "story-bible.sqlite"
TASK_LEASES_FILE = OUTPUT_ROOT / "narrative-cache" / "task-leases.sqlite"
WORKER_REGISTRY_FILE = OUTPUT_ROOT / "narrative-cache" / "worker-registry.sqlite"
MFLUX_FLUX2 = Path("/Users/aoo/AI/Tools/.uv-cache/archive-v0/X7bJU1XsIFmfYpPH/bin/mflux-generate-flux2")
MFLUX_FLUX2_EDIT = Path("/Users/aoo/AI/Tools/.uv-cache/archive-v0/X7bJU1XsIFmfYpPH/bin/mflux-generate-flux2-edit")
ASSET_3D_KLEIN9B_MODEL = os.environ.get("SHORT_DRAMA_KLEIN9B_MODEL", "mlx-community/flux2-klein-9b-8bit")
MFLUX_FLUX1 = Path("/Users/aoo/AI/Tools/.uv-cache/archive-v0/X7bJU1XsIFmfYpPH/bin/mflux-generate")
VISUAL_PERSONA_API_URL = os.environ.get("SHORT_DRAMA_VISUAL_PERSONA_API_URL", "").strip()
VISUAL_PERSONA_API_TOKEN = os.environ.get("SHORT_DRAMA_VISUAL_PERSONA_API_TOKEN", "").strip()
VISUAL_PERSONA_LICENSE_APPROVED = os.environ.get("SHORT_DRAMA_VISUAL_PERSONA_LICENSE_APPROVED", "").strip().lower() in {"1", "true", "yes"}
PSHUMAN_API_URL = os.environ.get("SHORT_DRAMA_PSHUMAN_API_URL", "").strip()
PSHUMAN_API_TOKEN = os.environ.get("SHORT_DRAMA_PSHUMAN_API_TOKEN", "").strip()
PSHUMAN_LICENSE_APPROVED = os.environ.get("SHORT_DRAMA_PSHUMAN_LICENSE_APPROVED", "").strip().lower() in {"1", "true", "yes"}
COMFY_PYTHON = Path("/Users/aoo/AI/Tools/ComfyUI/main/ComfyUI/.venv/bin/python3")
START_COMFY = Path("/Users/aoo/AI/Projects/ShortDramaPipeline/bin/start_comfy.py")
PIPELINE_ROOT = Path("/Users/aoo/AI/Projects/ShortDramaPipeline/pipeline")
LATENTSYNC_ROOT = Path("/Users/aoo/AI/Tools/LatentSync")
LATENTSYNC_MODELS = Path("/Users/aoo/AI/Models/Video/LatentSync-1.6")
FFMPEG = Path("/Users/aoo/AI/Tools/ComfyUI/main/ComfyUI/.venv/lib/python3.13/site-packages/imageio_ffmpeg/binaries/ffmpeg-macos-aarch64-v7.1")
COMFY_INPUT = Path("/Users/aoo/AI/ComfyUI-Shared/input")
COMFY_OUTPUT = Path("/Users/aoo/AI/ComfyUI-Shared/output")
COMFY_API = "http://127.0.0.1:8194"
H3_REF2VA_MODEL = "minimax_h3_ref2va_pruned_int8_convrot.safetensors"
H3_TEXT_ENCODER = "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"
H3_VIDEO_VAE = "minimax_h3_video_vae_fp16.safetensors"
H3_AUDIO_VAE = "minimax_h3_audio_vae_fp32.safetensors"
H3_CONTEXT_IR_MODEL = "qwen3-vl-h3-context-ir:latest"
H3_CONTEXT_IR_TIMEOUT_SECONDS = int(os.environ.get("SHORT_DRAMA_H3_CONTEXT_IR_TIMEOUT_SECONDS", "900"))
H3_CONTEXT_IR_OUTPUT_ROOT = OUTPUT_ROOT / "narrative-cache" / "h3-context-ir"
SERVICE_HOST = os.environ.get("SHORT_DRAMA_HOST", "127.0.0.1")
SERVICE_PORT = int(os.environ.get("SHORT_DRAMA_PORT", "8787"))
NARRATIVE_MODEL_REVIEW_ENABLED = os.environ.get("SHORT_DRAMA_NARRATIVE_REVIEW", "0").strip().lower() in {"1", "true", "yes"}
FLUX_LORA_GENERATOR = APPLICATION_ROOT / "plugins/builtin/short_drama/backend/flux_lora_generate.py"
IMAGE_TASK_SUPERVISOR = APPLICATION_ROOT / "plugins/builtin/short_drama/backend/image_task_supervisor.py"
ASSET_3D_WORKER = APPLICATION_ROOT / "plugins/builtin/short_drama/backend/asset_3d_worker.py"
TRIPOSR_PYTHON = Path("/Users/aoo/AI/Tools/TripoSR/.venv/bin/python")
TRIPOSR_MODEL = APPLICATION_ROOT / "models/3d/TripoSR/model.ckpt"
LORA_ROOT = APPLICATION_ROOT / "models/loras"
LORA_INDEX_FILE = LORA_ROOT / "模型索引.json"
COMMERCIAL_LORA_INDEX_FILE = LORA_ROOT / "商用LoRA索引.json"
KLEIN9B_TEST_LORA_INDEX_FILE = LORA_ROOT / "Flux2Klein9B测试LoRA索引.json"
CODEX_BINARY = Path("/Applications/ChatGPT.app/Contents/Resources/codex")
SYSTEM_AGENT_SKILLS = APPLICATION_ROOT / "plugins/builtin/system_agents/skills"
NARRATIVE_INPUT_SPEC = APPLICATION_ROOT / "plugins/builtin/short_drama/templates/prompts/AI_SHORT_DRAMA_PRODUCTION_SPEC.md"
HEAVY_TASK_LOCK = threading.RLock()
PRODUCTION_CAPABILITIES = production_capability_registry()
PRODUCTION_EXTENSIONS = production_extension_registry()
PRODUCTION_CAPABILITIES_INSTALL_LOCK = threading.Lock()
BUILTIN_PRODUCTION_CAPABILITIES_INSTALLED = False
LAST_COMFY_FREE_AT = 0.0
PROJECT_STORE_LOCK = threading.RLock()
PROJECT_STAGE_CONDITION = threading.Condition(PROJECT_STORE_LOCK)
PROJECT_STAGE_WATCH_LIMIT = max(8, int(os.environ.get("AI_PROJECT_STAGE_WATCH_LIMIT", "128")))
PROJECT_STAGE_WATCH_SLOTS = threading.BoundedSemaphore(PROJECT_STAGE_WATCH_LIMIT)
PROJECT_STAGE_CANCELLED_WATCHES: dict[tuple[str, str, str, str, str], float] = {}
SERVICE_SHUTTING_DOWN = threading.Event()
PRODUCTION_RESOURCE_POOLS = {
    "control":"control", "audio":"cpu-media",
    "text":"accelerator", "audit":"accelerator", "image":"accelerator",
    "video":"accelerator", "3d":"accelerator", "upscale":"accelerator",
}
PRODUCTION_POOL_CAPACITIES = {"accelerator":1, "cpu-media":2, "control":8}
PRODUCTION_POOL_QUEUE_LIMITS = {"accelerator":16, "cpu-media":64, "control":256}
PRODUCTION_TENANT_QUEUE_LIMITS = {"accelerator":8, "cpu-media":32, "control":128}
PRODUCTION_PROJECT_QUEUE_LIMITS = {"accelerator":4, "cpu-media":16, "control":64}
PRODUCTION_REQUEST_SCOPE = threading.local()


def _reap_cancelled_stage_watches(now: float | None = None) -> int:
    cutoff = (time.monotonic() if now is None else now) - 30
    with PROJECT_STAGE_CONDITION:
        stale = [request_id for request_id, cancelled_at in PROJECT_STAGE_CANCELLED_WATCHES.items() if cancelled_at <= cutoff]
        for request_id in stale: PROJECT_STAGE_CANCELLED_WATCHES.pop(request_id, None)
        return len(stale)


def _project_stage_watch_key(tenant_id: str, user_id: str, project_id: str, stage_name: str, request_id: str) -> tuple[str, str, str, str, str]:
    values = tuple(value.strip() for value in (tenant_id, user_id, project_id, stage_name, request_id))
    if any(not value for value in values) or len(values[-1]) > 128:
        raise ValueError("invalid_watch_scope")
    return values


def _monitor_project_stage_watches() -> None:
    while not SERVICE_SHUTTING_DOWN.wait(1):
        _reap_cancelled_stage_watches()


def _install_builtin_production_extensions() -> None:
    builtins = {
        "resource.scheduler": ("builtin.pooled_priority_resource_scheduler", lambda **values: ResourceScheduler(
            values.get("execution_lock"), resource_pools=values.get("resource_pools"),
            pool_capacities=values.get("pool_capacities"), pool_queue_limits=values.get("pool_queue_limits"),
            tenant_queue_limits=values.get("tenant_queue_limits"), project_queue_limits=values.get("project_queue_limits"),
            serialized_pools=set(values["serialized_pools"]) if values.get("serialized_pools") is not None else None,
        )),
        "storage.production_ledger": ("builtin.sqlite_production_ledger", lambda **values: ProductionLedger(Path(values["database"]))),
        "storage.story_bible": ("builtin.sqlite_story_bible", lambda **values: StoryBible(Path(values["database"]))),
        "storage.task_repository": ("builtin.sqlite_task_repository", lambda **values: DurableTaskRepository(Path(values["database"]))),
        "checkpoint.langgraph": ("builtin.langgraph_sqlite", lambda **values: ProductionOrchestrator(Path(values["database"]), values.get("director"))),
        "routing.workload": ("builtin.health_aware_workload_router", lambda **values: WorkloadRouter(heartbeat_timeout=float(values.get("heartbeat_timeout", 30)))),
        "storage.task_lease": ("builtin.sqlite_task_lease", lambda **values: TaskLeaseRepository(Path(values["database"]))),
        "discovery.workers": ("builtin.sqlite_worker_registry", lambda **values: WorkerRegistry(Path(values["database"]))),
    }
    contracts = {
        "resource.scheduler": ("claim", "snapshot", "cancel_job"),
        "storage.production_ledger": ("upsert", "list", "confirm"),
        "storage.story_bible": ("validate", "update"),
        "storage.task_repository": ("upsert_many", "list", "pending_projections", "acknowledge_projections", "projection_lock", "requeue_projection"),
        "checkpoint.langgraph": ("begin", "report", "state", "execute"),
        "routing.workload": ("route", "heartbeat", "reap"),
        "storage.task_lease": ("acquire", "renew", "release", "owns", "request_cancel", "cancellation_requested", "commit_guard", "reap_expired"),
        "discovery.workers": ("heartbeat", "list", "reap"),
    }
    implementation_types = {
        "resource.scheduler": ResourceScheduler,
        "storage.production_ledger": ProductionLedger,
        "storage.story_bible": StoryBible,
        "storage.task_repository": DurableTaskRepository,
        "checkpoint.langgraph": ProductionOrchestrator,
        "routing.workload": WorkloadRouter,
        "storage.task_lease": TaskLeaseRepository,
        "discovery.workers": WorkerRegistry,
    }
    for point, (provider, factory) in builtins.items():
        metadata = {
            "builtin": True, "hot_swappable": False, "contract_version": 1,
            "required_methods": contracts[point], "implementation_type": implementation_types[point],
        }
        if not PRODUCTION_EXTENSIONS.has(point, provider):
            PRODUCTION_EXTENSIONS.register(point, provider, factory, metadata=metadata)
        elif PRODUCTION_EXTENSIONS.get(point, provider).metadata.get("builtin"):
            PRODUCTION_EXTENSIONS.register(point, provider, factory, metadata=metadata, replace_provider=True)


_install_builtin_production_extensions()
RESOURCE_SCHEDULER = PRODUCTION_EXTENSIONS.create(
    "resource.scheduler", execution_lock=HEAVY_TASK_LOCK,
    resource_pools=PRODUCTION_RESOURCE_POOLS, pool_capacities=PRODUCTION_POOL_CAPACITIES,
    pool_queue_limits=PRODUCTION_POOL_QUEUE_LIMITS,
    tenant_queue_limits=PRODUCTION_TENANT_QUEUE_LIMITS, project_queue_limits=PRODUCTION_PROJECT_QUEUE_LIMITS,
    serialized_pools={"accelerator"},
)
PRODUCTION_LEDGER = PRODUCTION_EXTENSIONS.create("storage.production_ledger", database=PRODUCTION_LEDGER_FILE)
STORY_BIBLE = PRODUCTION_EXTENSIONS.create("storage.story_bible", database=STORY_BIBLE_FILE)
WORKLOAD_ROUTER = PRODUCTION_EXTENSIONS.create("routing.workload", heartbeat_timeout=30)
TASK_LEASES = PRODUCTION_EXTENSIONS.create("storage.task_lease", database=TASK_LEASES_FILE)
WORKER_REGISTRY = PRODUCTION_EXTENSIONS.create("discovery.workers", database=WORKER_REGISTRY_FILE)
WORKER_ID = os.environ.get("SHORT_DRAMA_WORKER_ID", f"{os.uname().nodename}-{os.getpid()}")
WORKER_SCOPE = os.environ.get("SHORT_DRAMA_WORKER_SCOPE", "local-production")
WORKER_HEARTBEAT_STOP = threading.Event()


def _heartbeat_local_worker() -> WorkerSnapshot:
    resources = RESOURCE_SCHEDULER.snapshot()
    WORKLOAD_ROUTER.reap()
    try:
        available_memory = _memory_limits()[1]
    except Exception:
        available_memory = 1 << 60
    worker = WorkerSnapshot(
        worker_id=WORKER_ID, service_scope=WORKER_SCOPE,
        resource_classes=("control", "text", "audit", "image", "audio", "video", "3d", "upscale"),
        capacity=sum(PRODUCTION_POOL_CAPACITIES.values()), active=len(resources.get("active_items") or []),
        queue_depth=len(resources.get("queued") or []), available_memory=available_memory,
        heartbeat_at=time.time(), generation=1,
        endpoint=f"http://{SERVICE_HOST}:{SERVICE_PORT}",
    )
    WORKER_REGISTRY.heartbeat(worker)
    for discovered in WORKER_REGISTRY.list(heartbeat_timeout=30, service_scope=WORKER_SCOPE):
        WORKLOAD_ROUTER.heartbeat(discovered)
    return WORKLOAD_ROUTER.heartbeat(worker)


def _monitor_local_worker() -> None:
    while not WORKER_HEARTBEAT_STOP.is_set():
        _heartbeat_local_worker(); TASK_LEASES.reap_expired(); WORKER_REGISTRY.reap(heartbeat_timeout=30); WORKLOAD_ROUTER.reap(); _replay_durable_task_projections()
        WORKER_HEARTBEAT_STOP.wait(10)


def _production_identity(payload: dict | None) -> dict[str, str]:
    payload = payload or {}
    identity = {
        "tenant_id":str(payload.get("tenant_id") or "local-default").strip(),
        "user_id":str(payload.get("user_id") or "aoo").strip(),
        "project_id":str(payload.get("project_id") or "").strip(),
    }
    return identity if identity["project_id"] else {}


@contextmanager
def _claim_production_resource(resource_class: str, job_id: str, *, estimated_memory: int = 0, timeout: float | None = None,
                               identity: dict | None = None):
    """Distributed admission + fencing lease around the existing local scheduler."""
    worker = _heartbeat_local_worker()
    WORKLOAD_ROUTER.route(resource_class, estimated_memory=estimated_memory, service_scope=WORKER_SCOPE, worker_id=WORKER_ID)
    lease_owner = f"{WORKER_ID}:{uuid4().hex}"
    lease = TASK_LEASES.acquire(str(job_id), lease_owner, ttl=45)
    stop_renewal = threading.Event()
    renewal_failed = threading.Event()
    def renew() -> None:
        while not stop_renewal.wait(10):
            if not TASK_LEASES.renew(str(job_id), lease_owner, int(lease["generation"]), ttl=45):
                renewal_failed.set(); return
            _heartbeat_local_worker()
    renewal = threading.Thread(target=renew, name=f"task-lease-{job_id}", daemon=True); renewal.start()
    try:
        scope = _production_identity(identity) if identity is not None else getattr(PRODUCTION_REQUEST_SCOPE, "identity", {})
        with RESOURCE_SCHEDULER.claim(
            resource_class, str(job_id), estimated_memory=estimated_memory, timeout=timeout,
            tenant_id=str(scope.get("tenant_id") or ""), user_id=str(scope.get("user_id") or ""),
            project_id=str(scope.get("project_id") or ""),
        ) as ticket:
            if renewal_failed.is_set() or not TASK_LEASES.owns(str(job_id), lease_owner, int(lease["generation"])):
                raise RuntimeError("task ownership lease lost")
            yield ticket
            if renewal_failed.is_set() or not TASK_LEASES.owns(str(job_id), lease_owner, int(lease["generation"])):
                raise RuntimeError("task ownership lease lost before result commit")
    finally:
        stop_renewal.set(); renewal.join(timeout=1)
        TASK_LEASES.release(str(job_id), lease_owner, int(lease["generation"]))
        _heartbeat_local_worker()
PRODUCTION_ORCHESTRATOR: ProductionOrchestrator | None = None
PRODUCTION_ORCHESTRATOR_LOCK = threading.Lock()
ACTIVE_PRODUCTION_STAGE_REQUESTS: set[str] = set()
ACTIVE_PRODUCTION_STAGE_REQUESTS_LOCK = threading.Lock()
ACTIVE_PRODUCTION_STAGE_CANCEL_EVENTS: dict[str, threading.Event] = {}
TASK_REPOSITORIES: dict[Path, DurableTaskRepository] = {}
TASK_REPOSITORIES_LOCK = threading.Lock()


def _task_repository(job_file: Path) -> DurableTaskRepository:
    database = job_file.parent.resolve() / "unified-tasks.sqlite"
    with TASK_REPOSITORIES_LOCK:
        repository = TASK_REPOSITORIES.get(database)
        if repository is None:
            repository = PRODUCTION_EXTENSIONS.create("storage.task_repository", database=database)
            TASK_REPOSITORIES[database] = repository
    return repository


def _production_stage_lease_key(body: dict, stage: str) -> str:
    identity = [str(body.get(name) or "").strip() for name in ("tenant_id", "user_id", "project_id")]
    if not all(identity):
        raise ValueError("tenant_id, user_id and project_id are required for production stage execution")
    return "production-stage:" + ":".join((*identity, canonical_stage(stage)))


@contextmanager
def _claim_production_stage_request(body: dict, stage: str):
    key = ":".join(str(body.get(name) or "") for name in ("tenant_id", "user_id", "project_id")) + f":{stage}"
    lease_key = _production_stage_lease_key(body, stage)
    owner_id = f"{WORKER_ID}:{uuid4().hex}"
    with ACTIVE_PRODUCTION_STAGE_REQUESTS_LOCK:
        if key in ACTIVE_PRODUCTION_STAGE_REQUESTS:
            raise ValueError(f"production stage is already running: {stage}")
    try:
        lease = TASK_LEASES.acquire(lease_key, owner_id, ttl=45)
    except TaskLeaseError as error:
        raise ValueError(f"production stage is already running: {stage}") from error
    cancel_event = threading.Event()
    with ACTIVE_PRODUCTION_STAGE_REQUESTS_LOCK:
        ACTIVE_PRODUCTION_STAGE_REQUESTS.add(key)
        ACTIVE_PRODUCTION_STAGE_CANCEL_EVENTS[key] = cancel_event
    stop_renewal = threading.Event()
    generation = int(lease["generation"])
    cancel_event.lease_key = lease_key  # type: ignore[attr-defined]
    cancel_event.lease_owner = owner_id  # type: ignore[attr-defined]
    cancel_event.lease_generation = generation  # type: ignore[attr-defined]
    def renew_stage_lease() -> None:
        while not stop_renewal.wait(1):
            try:
                renewed = TASK_LEASES.renew(lease_key, owner_id, generation, ttl=45)
            except Exception:
                renewed = False
            if not renewed:
                try:
                    cancel_event.cancel_requested = TASK_LEASES.cancellation_requested(lease_key, owner_id, generation)  # type: ignore[attr-defined]
                except Exception:
                    cancel_event.cancel_requested = False  # type: ignore[attr-defined]
                cancel_event.set()
                return
    renewal = threading.Thread(target=renew_stage_lease, daemon=True, name=f"stage-lease-{stage}-{generation}")
    renewal.start()
    try:
        yield cancel_event
        if not bool(getattr(cancel_event, "commit_completed", False)) and (
            cancel_event.is_set() or not TASK_LEASES.owns(lease_key, owner_id, generation)
        ):
            raise RuntimeError(f"production stage cancelled or lease lost: {stage}")
    finally:
        stop_renewal.set(); renewal.join(timeout=1)
        try:
            TASK_LEASES.release(lease_key, owner_id, generation)
        except Exception:
            pass
        with ACTIVE_PRODUCTION_STAGE_REQUESTS_LOCK:
            ACTIVE_PRODUCTION_STAGE_REQUESTS.discard(key)
            if ACTIVE_PRODUCTION_STAGE_CANCEL_EVENTS.get(key) is cancel_event:
                ACTIVE_PRODUCTION_STAGE_CANCEL_EVENTS.pop(key, None)


def _ensure_production_stage_request_active(cancel_event: threading.Event, stage: str) -> None:
    lease_key = str(getattr(cancel_event, "lease_key", ""))
    owner_id = str(getattr(cancel_event, "lease_owner", ""))
    generation = int(getattr(cancel_event, "lease_generation", 0) or 0)
    owns = bool(lease_key) and TASK_LEASES.owns(lease_key, owner_id, generation)
    if cancel_event.is_set() or not owns:
        try:
            cancel_event.cancel_requested = TASK_LEASES.cancellation_requested(lease_key, owner_id, generation)  # type: ignore[attr-defined]
        except Exception:
            cancel_event.cancel_requested = False  # type: ignore[attr-defined]
        cancel_event.set()
        raise RuntimeError(f"production stage cancelled or lease lost: {stage}")


@contextmanager
def _production_stage_commit_guard(cancel_event: threading.Event, stage: str):
    lease_key = str(getattr(cancel_event, "lease_key", ""))
    owner_id = str(getattr(cancel_event, "lease_owner", ""))
    generation = int(getattr(cancel_event, "lease_generation", 0) or 0)
    try:
        with TASK_LEASES.commit_guard(lease_key, owner_id, generation):
            if cancel_event.is_set():
                raise TaskLeaseError("production stage cancellation won before commit")
            yield
        cancel_event.commit_completed = True  # type: ignore[attr-defined]
    except TaskLeaseError as error:
        try:
            cancel_event.cancel_requested = TASK_LEASES.cancellation_requested(lease_key, owner_id, generation)  # type: ignore[attr-defined]
        except Exception:
            cancel_event.cancel_requested = False  # type: ignore[attr-defined]
        cancel_event.set()
        raise RuntimeError(f"production stage cancelled or lease lost: {stage}") from error


def _commit_server_production_stage_result(
    body: dict,
    stage: str,
    result: dict,
    cancel_event: threading.Event,
    stage_generation: int,
) -> dict:
    """Publish business evidence and Graph state under one fenced commit."""
    with _production_stage_commit_guard(cancel_event, stage):
        if stage == "assets":
            census = dict(result.get("census") or {})
            written = _write_project_stage(
                str(body.get("project_id") or ""), str(body.get("tenant_id") or "local-default"), str(body.get("user_id") or "aoo"), "assets",
                {"_merge_existing":True, "characters":result.get("characters") or [], "scenes":result.get("scenes") or [], "props":result.get("props") or [],
                 "status":"waiting_confirmation", "error":"", "source_episodes":census.get("episodes") or body.get("target_episodes") or [], "census_version":2},
                stage_generation=stage_generation,
            )
            return written["workflow"]
        if stage == "review_export" and result.get("operation") == "upscale":
            authority_records = result.pop("_authority_records", None)
            if not isinstance(authority_records, list) or not authority_records:
                raise RuntimeError("upscale authority commit payload is missing")
            workflow_holder: dict[str, dict] = {}

            def commit_graph() -> None:
                authority_commit = {
                    "kind":"upscale",
                    "records":[{
                        "scope_id":str(item["scope_id"]),
                        "generation":int(item["generation"]),
                        "content_fingerprint":str(item["content_fingerprint"]),
                        "audit_batch_id":str(item["audit_batch_id"]),
                    } for item in authority_records],
                }
                workflow_holder["workflow"] = _production_orchestrator().report(
                    body, stage, "pending_confirmation", evidence={"server_coordinated":True},
                    authority_commit=authority_commit, stage_generation=stage_generation,
                    projection_revision=1,
                )

            PRODUCTION_LEDGER.commit_upscale_authorities(
                authority_records, commit_callback=commit_graph,
            )
            return workflow_holder["workflow"]
        return _production_orchestrator().report(
            body, stage, "pending_confirmation", evidence={"server_coordinated":True},
            stage_generation=stage_generation, projection_revision=1,
        )


def _cancel_production_stage(body: dict, stage: str) -> int:
    tenant_id = str(body.get("tenant_id") or "").strip()
    user_id = str(body.get("user_id") or "").strip()
    project_id = str(body.get("project_id") or "").strip()
    if not tenant_id or not user_id or not project_id:
        raise ValueError("tenant_id, user_id and project_id are required for targeted stage cancellation")
    target_key = f"{tenant_id}:{user_id}:{project_id}:{stage}"
    cancelled = int(TASK_LEASES.request_cancel(_production_stage_lease_key(body, stage)))
    if cancelled:
        with ACTIVE_PRODUCTION_STAGE_REQUESTS_LOCK:
            event = ACTIVE_PRODUCTION_STAGE_CANCEL_EVENTS.get(target_key)
            if event is not None:
                event.cancel_requested = True  # type: ignore[attr-defined]
                event.set()
    return cancelled


def _cancel_scoped_production_stage(body: dict, stage: str) -> int:
    """Cancel only the exact tenant/user/project stage when full identity exists."""
    if not all(str(body.get(key) or "").strip() for key in ("tenant_id", "user_id", "project_id")):
        return 0
    return _cancel_production_stage(body, canonical_stage(stage))


def _sync_durable_tasks(task_class: str, job_file: Path, store: dict) -> None:
    repository = _task_repository(job_file)
    jobs = store.get("jobs", {}) if isinstance(store, dict) else {}
    if not isinstance(jobs, dict):
        return
    repository.upsert_many(task_class, {str(job_id):job for job_id, job in jobs.items() if isinstance(job, dict)}, enqueue_projection=True)
    _drain_durable_task_projections(task_class, job_file)


def _durable_task_projection(task_class: str, job: dict) -> tuple[tuple[str, str, str, str], str] | None:
    request = job.get("request") if isinstance(job.get("request"), dict) else {}
    identity = tuple(str(job.get(key) or request.get(key) or "").strip() for key in ("tenant_id", "user_id", "project_id"))
    endpoint = str(job.get("endpoint") or request.get("endpoint") or "")
    raw_stage = str(job.get("stage") or job.get("phase") or "")
    if task_class == "text" and raw_stage in {"outline", "script"}: stage = raw_stage
    elif task_class == "image":
        # Asset census/extraction owns the assets stage. Every 2D render,
        # including character/scene/prop baselines and shot images, owns image.
        # TripoSR/Blender remains an assets-stage 3D subtask by contract.
        stage = "assets" if job.get("workflow") == "asset_3d" else "image"
    elif task_class == "video": stage = "video"
    else: stage = ""
    lifecycle_map = {
        "queued":"queued", "waiting_memory":"queued", "generating":"running", "running":"running",
        "retrying":"running", "processing":"running", "completed":"pending_confirmation", "failed":"failed",
        "paused":"paused", "cancelled":"cancelled",
    }
    lifecycle = lifecycle_map.get(str(job.get("status") or ""))
    return ((*identity, stage), lifecycle) if all(identity) and stage and lifecycle else None


def _drain_durable_task_projections(task_class: str, job_file: Path) -> int:
    repository = _task_repository(job_file)
    if job_file.parent.resolve() != (OUTPUT_ROOT / "narrative-cache").resolve():
        return 0
    if SERVICE_SHUTTING_DOWN.is_set():
        return 0
    grouped: dict[tuple[str, str, str, str], list[dict]] = {}
    ignored: list[tuple[str, int]] = []
    for item in repository.pending_projections(task_class=task_class):
        projection = _durable_task_projection(task_class, item["payload"])
        if projection is None:
            ignored.append((str(item["job_id"]), int(item["event_revision"]))); continue
        grouped.setdefault(projection[0], []).append({**item, "lifecycle":projection[1]})
    acknowledged = repository.acknowledge_projections(ignored)
    for tenant_id, user_id, project_id, stage in grouped:
        if SERVICE_SHUTTING_DOWN.is_set():
            break
        scope_key = ":".join((tenant_id, user_id, project_id, stage))
        with repository.projection_lock(scope_key) as lease:
            if not lease or SERVICE_SHUTTING_DOWN.is_set() or not lease.owns():
                continue
            items = []
            for item in repository.pending_projections(task_class=task_class):
                projection = _durable_task_projection(task_class, item["payload"])
                if projection and projection[0] == (tenant_id, user_id, project_id, stage):
                    items.append({**item, "lifecycle":projection[1]})
            if not items:
                continue
            latest = max(items, key=lambda item:(int(item["event_revision"]), str(item.get("job_id") or "")))
            job = latest["payload"]
            if not lease.owns():
                continue
            try:
                _production_orchestrator().report(
                    {"tenant_id":tenant_id, "user_id":user_id, "project_id":project_id}, stage, latest["lifecycle"],
                    job_id=str(job.get("job_id") or ""), error=str(job.get("error") or ""),
                    projection_revision=int(latest["event_revision"]),
                )
            except Exception:
                continue
            # A lease can be lost while the external graph checkpoint is being
            # committed. Re-enqueue the authoritative task with a newer fence so
            # a later projector repairs any stale checkpoint instead of silently
            # acknowledging the newer event.
            if not lease.owns() or SERVICE_SHUTTING_DOWN.is_set():
                repository.requeue_projection(str(latest["job_id"]))
                continue
            acknowledged += repository.acknowledge_projections([
                (str(item["job_id"]), int(item["event_revision"])) for item in items
            ])
    return acknowledged


def _replay_durable_task_projections() -> int:
    acknowledged = 0
    for task_class, job_file in (("text", TEXT_JOBS_FILE), ("image", IMAGE_JOBS_FILE), ("video", VIDEO_JOBS_FILE)):
        try:
            acknowledged += _drain_durable_task_projections(task_class, job_file)
        except Exception:
            # Projection is an outbox-backed compatibility operation. A busy or
            # temporarily unavailable store must leave the event pending for the
            # next heartbeat, never terminate the worker heartbeat itself.
            continue
    return acknowledged


def _merge_durable_tasks(task_class: str, job_file: Path, store: dict) -> dict:
    jobs = store.setdefault("jobs", {})
    if not isinstance(jobs, dict):
        jobs = {}; store["jobs"] = jobs
    for record in _task_repository(job_file).list(task_class=task_class):
        payload = record.get("payload")
        if isinstance(payload, dict):
            # Legacy rows may have lifecycle columns but an incomplete payload
            # (for example no status/job_id/identity). Recovery operates on the
            # merged payload, so preserve the authoritative repository columns
            # whenever the historical payload omitted them.
            merged = dict(payload)
            for key in ("job_id", "tenant_id", "user_id", "project_id", "stage", "subject_key", "status",
                        "pid", "process_group", "heartbeat_at", "started_at", "finished_at"):
                if key not in merged and record.get(key) not in {None, ""}:
                    merged[key] = record[key]
            # Very old image rows can have no recoverable project identity at
            # all.  Never fabricate membership in a real project and never
            # silently acknowledge their projection.  Give only stale/recovered
            # rows a deterministic tenant-scoped quarantine identity so their
            # terminal recovery is auditable in LangGraph.
            if task_class == "image" and not str(merged.get("project_id") or "").strip() and (
                str(merged.get("status") or "") in {"queued", "generating", "retrying", "processing"}
                or str(merged.get("error") or "") == "服务重启已回收残留图片任务，请重新生成"
            ):
                merged["project_id"] = f"recovered-orphan-image-{record['job_id']}"
                merged["identity_recovery"] = "quarantined_missing_project"
                merged["subject_key"] = merged.get("subject_key") or ":".join((
                    str(merged.get("tenant_id") or "local-default"), str(merged.get("user_id") or "local"),
                    str(merged["project_id"]), "recovery",
                ))
            jobs[str(record["job_id"])] = merged
    return store


def _heavy_task_busy() -> bool:
    return any(item.get("pool") == "accelerator" for item in RESOURCE_SCHEDULER.snapshot().get("active_items", []))
SYSTEM_AGENT_LOCK = threading.Lock()
AGENT_JOB_LOCK = threading.Lock()
ACTIVE_AGENT_JOBS: set[str] = set()
IMAGE_JOB_LOCK = threading.Lock()
ACTIVE_IMAGE_JOBS: set[str] = set()
ACTIVE_IMAGE_SUBJECTS: dict[str, str] = {}
ACTIVE_IMAGE_PROCESSES: dict[str, subprocess.Popen[str]] = {}
ACTIVE_IMAGE_WORKERS: dict[str, threading.Thread] = {}
IMAGE_TASK_TIMEOUT_SECONDS = max(60, int(os.environ.get("SHORT_DRAMA_IMAGE_TASK_TIMEOUT_SECONDS", "1800")))
IMAGE_QUEUE_TIMEOUT_SECONDS = max(60, int(os.environ.get("SHORT_DRAMA_IMAGE_QUEUE_TIMEOUT_SECONDS", "600")))
IMAGE_VALIDATION_TIMEOUT_SECONDS = max(30, int(os.environ.get("SHORT_DRAMA_IMAGE_VALIDATION_TIMEOUT_SECONDS", "180")))
IMAGE_WATCHDOG_SECONDS = max(1, int(os.environ.get("SHORT_DRAMA_IMAGE_WATCHDOG_SECONDS", "5")))
IMAGE_WATCHDOG_STOP = threading.Event()
IMAGE_SHUTTING_DOWN = threading.Event()
TEXT_JOB_LOCK = threading.RLock()
ACTIVE_TEXT_JOBS: dict[str, dict] = {}
FORMAL_MODEL_OWNER_LOCK = threading.Lock()
FORMAL_MODEL_OWNER_JOB_ID = ""
TEXT_JOB_TIMEOUT_SECONDS = max(60, int(os.environ.get("SHORT_DRAMA_TEXT_TASK_TIMEOUT_SECONDS", "330")))
OUTLINE_JOB_TIMEOUT_SECONDS = max(600, int(os.environ.get("SHORT_DRAMA_OUTLINE_TASK_TIMEOUT_SECONDS", "1800")))
TEXT_WATCHDOG_SECONDS = max(1, int(os.environ.get("SHORT_DRAMA_TEXT_WATCHDOG_SECONDS", "5")))
TEXT_WATCHDOG_STOP = threading.Event()
COMFY_TEMP_PREFIXES = (
    "short_drama_qwen_repairs",
    "short_drama_refs", "short_drama_clothing_refs", "short_drama_pose_refs",
    "short_drama_depth_refs", "short_drama_masks", "short_drama_pose_input",
)
VIDEO_JOB_LOCK = threading.Lock()
ACTIVE_VIDEO_JOBS: set[str] = set()
ACTIVE_VIDEO_SUBJECTS: dict[str, str] = {}
ACTIVE_VIDEO_PROCESSES: dict[str, subprocess.Popen[str]] = {}
ACTIVE_VIDEO_PROMPT_CANCELLERS: set[str] = set()
VIDEO_MEMORY_MONITOR_STOP = threading.Event()
VIDEO_TASK_TIMEOUT_SECONDS = max(300, int(os.environ.get("SHORT_DRAMA_VIDEO_TASK_TIMEOUT_SECONDS", "14400")))
VIDEO_QUEUE_TIMEOUT_SECONDS = max(60, int(os.environ.get("SHORT_DRAMA_VIDEO_QUEUE_TIMEOUT_SECONDS", "1800")))
VIDEO_WATCHDOG_SECONDS = max(1, int(os.environ.get("SHORT_DRAMA_VIDEO_WATCHDOG_SECONDS", "5")))
GIB = 1024 ** 3
VIDEO_ESTIMATED_MEMORY = 48 * GIB
TEXT_LIGHT_MODEL = "qwen3.5:9b-q4_K_M"
TEXT_FORMAL_MODEL = "qwen3-vl:32b"
TEXT_AUDIT_MODEL = "qwen2.5:72b"
TEXT_AUDIT_MODEL_PATH = Path(os.environ.get(
    "SHORT_DRAMA_QWEN35_122B_PATH",
    "/Users/aoo/AI/Models/Text/Qwen3.5-122B-A10B-mxfp4",
))
MLX_VLM_PYTHON = Path(os.environ.get(
    "SHORT_DRAMA_MLX_VLM_PYTHON",
    "/Users/aoo/.local/share/uv/tools/mlx-vlm/bin/python",
))
MLX_JSON_WORKER = APPLICATION_ROOT / "plugins/builtin/short_drama/backend/mlx_json_worker.py"
TEXT_LIGHT_ESTIMATED_MEMORY = 10 * GIB
TEXT_FORMAL_ESTIMATED_MEMORY = 38 * GIB
TEXT_AUDIT_ESTIMATED_MEMORY = 62 * GIB
MEMORY_POLL_SECONDS = 5
PRODUCTION_FRAME_RATE = 30


PRODUCTION_SPEC_SECTIONS = {
    "outline": ("一", "十二", "十三"),
    "script": ("一", "二", "七", "八", "十二", "十三"),
    "storyboard": ("二", "三", "九", "十", "十一", "十二", "十三"),
    "assets": ("四", "十", "十一", "十三"),
    "image": ("四", "五", "十", "十一", "十三"),
    "video": ("三", "五", "九", "十", "十一", "十二", "十三"),
    "audio": ("六", "七", "八", "十三"),
    "post": ("五", "六", "七", "八", "九", "十四"),
    "final": ("十", "十一", "十二", "十四"),
}


def _read_production_spec() -> str:
    """Read the live master specification on every production request."""
    try:
        content = NARRATIVE_INPUT_SPEC.read_text(encoding="utf-8").strip()
    except OSError as error:
        raise RuntimeError(f"无法读取全流程投产规范：{NARRATIVE_INPUT_SPEC}") from error
    if not content:
        raise RuntimeError(f"全流程投产规范为空：{NARRATIVE_INPUT_SPEC}")
    return content


def _production_spec_for(stage: str) -> str:
    """Index only the authoritative sections needed by the active workflow."""
    content = _read_production_spec()
    marker_matches = list(re.finditer(r"(?m)^\s*<!--\s*AI_SPEC_SECTION:(一|二|三|四|五|六|七|八|九|十|十一|十二|十三|十四)\s*-->\s*$", content))
    matches = marker_matches or list(re.finditer(r"(?m)^\s{0,3}(?:#{1,6}\s*)?(一|二|三|四|五|六|七|八|九|十|十一|十二|十三|十四)、[^\n]*", content))
    preamble = content[:matches[0].start()].strip() if matches else ""
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
        sections[match.group(1)] = content[match.start():end].strip()
    required = PRODUCTION_SPEC_SECTIONS.get(stage)
    if not required:
        raise ValueError(f"未知投产流程：{stage}")
    missing = [name for name in required if name not in sections]
    if missing:
        raise RuntimeError(f"全流程投产规范缺少章节：{', '.join(missing)}")
    selected = "\n\n".join(sections[name] for name in required)
    return f"{preamble}\n\n{selected}" if preamble else selected


def _normalized_story_text(value: object) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff]+", "", str(value or "")).lower()


OUTLINE_REQUIRED_FIELDS = (
    "story_stage", "core_event", "protagonist_action", "ability_progression",
    "villain_action", "supporting_motivation", "protection_set_piece",
    "irreversible_change", "new_information", "resolved_setup", "cliffhanger",
)


def _canonical_story_text(value: object) -> str:
    text = _normalized_story_text(value)
    synonyms = (
        (("策反", "收买", "买通", "笼络"), "操控"),
        (("围堵", "围困", "包围", "堵截", "伏击"), "围剿"),
        (("伪造", "假造", "捏造", "栽赃", "污蔑"), "诬陷"),
        (("盗走", "偷走", "窃取", "抢走", "夺走"), "夺取"),
        (("揭穿", "揭露", "识破", "查明"), "查清"),
        (("退位", "撤职", "罢免", "逐出"), "失势"),
    )
    for words, canonical in synonyms:
        for word in words:
            text = text.replace(word, canonical)
    return text


def _story_ngrams(value: object, size: int = 2) -> set[str]:
    text = _canonical_story_text(value)
    return {text[index:index + size] for index in range(max(0, len(text) - size + 1))}


def _story_similarity(left: object, right: object) -> float:
    left_set, right_set = _story_ngrams(left), _story_ngrams(right)
    if not left_set or not right_set:
        return 0.0
    return len(left_set & right_set) / len(left_set | right_set)


def _story_stage_number(value: object) -> int | None:
    match = re.match(r"^第?(\d+)集(?:[·：:—-]|$)", str(value or "").strip())
    return int(match.group(1)) if match else None


def _irreversible_similarity(left: object, right: object) -> float:
    generic = ("永久", "永远", "再也", "不能", "无法", "失去", "不可恢复", "不可逆")
    left_text, right_text = _canonical_story_text(left), _canonical_story_text(right)
    for word in generic:
        left_text = left_text.replace(word, "")
        right_text = right_text.replace(word, "")
    return _story_similarity(left_text, right_text)


def _ability_level(value: object) -> int | None:
    text = str(value or "")
    match = re.search(r"([一二三四五六七八九十\d]+)阶", text)
    if not match:
        return None
    raw = match.group(1)
    if raw.isdigit():
        return int(raw)
    digits = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
    return digits.get(raw)


def _ability_has_cost(value: object) -> bool:
    text = str(value or "")
    if any(phrase in text for phrase in ("无需代价", "没有代价", "无任何代价", "不需代价", "不消耗", "零消耗", "无副作用", "没有限制")):
        return False
    return any(word in text for word in ("代价", "消耗", "损耗", "反噬", "虚弱", "失去", "限制", "冷却", "昏迷", "受伤"))


def _conflict_signature(value: object) -> set[str]:
    text = str(value or "")
    groups = {
        "诬陷": ("诬陷", "栽赃", "造谣", "污蔑"),
        "夺取": ("夺取", "抢夺", "盗取", "窃取", "夺血"),
        "操控": ("操控", "策反", "收买", "控制长老", "挑拨"),
        "围剿": ("围剿", "追杀", "伏杀", "暗杀", "截杀"),
        "毒害": ("下毒", "下药", "投毒", "投药", "毒杀", "毒害", "毒雾", "毒粉", "毒丹", "毒酒", "毒药", "噬灵虫", "蛊毒"),
        "试炼": ("试炼", "考核", "闯关"),
        "证据救场": ("证据", "记录", "揭露", "证明清白"),
        "护主救场": ("护短", "挡在", "挺身而出", "救下", "护在身后"),
        "血脉爆发": ("血脉爆发", "血脉觉醒", "觉醒反击", "释放血脉"),
    }
    return {name for name, words in groups.items() if any(word in text for word in words)}


def _validate_outline_episode_batch(episodes: object, start: int, count: int, previous: object) -> list[dict]:
    if not isinstance(episodes, list) or len(episodes) != count:
        raise ValueError(f"分集梗概必须正好返回{count}集")
    prior = previous if isinstance(previous, list) else []
    prior_titles = {_normalized_story_text(item.get("title")) for item in prior if isinstance(item, dict)}
    prior_synopses = {_normalized_story_text(item.get("synopsis")) for item in prior if isinstance(item, dict)}
    seen_titles = set(prior_titles)
    seen_synopses = set(prior_synopses)
    prior_items = [item for item in prior if isinstance(item, dict)]
    normalized: list[dict] = []
    for offset, item in enumerate(episodes):
        if not isinstance(item, dict):
            raise ValueError("分集梗概条目必须是JSON对象")
        expected = start + offset
        if int(item.get("episode") or 0) != expected:
            raise ValueError(f"分集编号错误：期望第{expected}集")
        title = _normalized_story_text(item.get("title"))
        synopsis = _normalized_story_text(item.get("synopsis"))
        if not title or not synopsis:
            raise ValueError(f"第{expected}集标题或梗概为空")
        if title in seen_titles:
            raise ValueError(f"第{expected}集标题与既有分集重复")
        if synopsis in seen_synopses:
            raise ValueError(f"第{expected}集核心梗概与既有分集重复")
        missing = [field for field in OUTLINE_REQUIRED_FIELDS if not str(item.get(field, "")).strip()]
        if missing:
            raise ValueError(f"第{expected}集缺少全剧状态字段：{', '.join(missing)}")
        cliffhanger = str(item.get("cliffhanger", ""))
        if any(phrase in cliffhanger for phrase in ("阴谋仍在", "威胁逼近", "危机还未结束", "真相即将揭晓", "更大的阴谋")):
            raise ValueError(f"第{expected}集结尾悬念不具象")
        if len(_normalized_story_text(cliffhanger)) < 8:
            raise ValueError(f"第{expected}集结尾悬念信息不足")
        stage_number = _story_stage_number(item.get("story_stage"))
        if stage_number is None:
            item["story_stage"] = f"第{expected}集·{str(item.get('story_stage', '')).strip()}"
        elif stage_number != expected:
            raise ValueError(f"第{expected}集剧情阶段必须以‘第{expected}集·’开头，禁止阶段倒流")
        if not _ability_has_cost(item.get("ability_progression")):
            raise ValueError(f"第{expected}集能力推进缺少明确代价或限制")
        current_conflict = _conflict_signature(f"{item.get('villain_action', '')}{item.get('core_event', '')}{item.get('synopsis', '')}")
        current_villain_conflict = _conflict_signature(item.get("villain_action", ""))
        for prior_item in [*prior_items, *normalized]:
            prior_episode = prior_item.get("episode", "?")
            if _story_similarity(item.get("title"), prior_item.get("title")) >= 0.30:
                raise ValueError(f"第{expected}集标题与第{prior_episode}集语义重复")
            if _story_similarity(item.get("core_event"), prior_item.get("core_event")) >= 0.42:
                raise ValueError(f"第{expected}集核心事件与第{prior_episode}集语义重复")
            if _story_similarity(item.get("villain_action"), prior_item.get("villain_action")) >= 0.32:
                raise ValueError(f"第{expected}集反派手段与第{prior_episode}集重复")
            prior_villain_conflict = _conflict_signature(prior_item.get("villain_action", ""))
            if current_villain_conflict & prior_villain_conflict:
                raise ValueError(f"第{expected}集反派手段与第{prior_episode}集同类重复")
            if _irreversible_similarity(item.get("irreversible_change"), prior_item.get("irreversible_change")) >= 0.25:
                raise ValueError(f"第{expected}集不可逆变化与第{prior_episode}集重复")
            current_level = _ability_level(item.get("ability_progression"))
            prior_level = _ability_level(prior_item.get("ability_progression"))
            if current_level is not None and prior_level is not None and current_level < prior_level:
                raise ValueError(f"第{expected}集能力等级低于第{prior_episode}集，禁止能力退阶")
            prior_conflict = _conflict_signature(f"{prior_item.get('villain_action', '')}{prior_item.get('core_event', '')}{prior_item.get('synopsis', '')}")
            if current_conflict and len(current_conflict & prior_conflict) >= 3:
                raise ValueError(f"第{expected}集冲突流程与第{prior_episode}集模板化重复")
        seen_titles.add(title)
        seen_synopses.add(synopsis)
        normalized.append(item)
    return normalized


def _script_dialogue_lines(script: object) -> list[str]:
    lines: list[str] = []
    for raw in str(script or "").splitlines():
        field_match = re.match(r"^\s*(?:台词|旁白)\s*[：:]\s*(.+?)\s*$", raw)
        if field_match:
            text = _normalized_story_text(field_match.group(1))
            if text and text not in {"无", "无对白", "无台词"} and len(text) <= 60:
                lines.append(text)
            continue
        if re.match(r"^\s*(?:画面|动作|情绪|时间段)\s*[：:]", raw):
            continue
        match = re.match(r"^\s*([^【\[：:\n]{1,30}(?:（[^）]*）|\([^)]*\))?)\s*[：:]\s*(.+?)\s*$", raw)
        if match:
            text = _normalized_story_text(f"{match.group(1)}{match.group(2)}")
            if text and len(text) <= 40:
                lines.append(text)
    return lines


def _human_readable_script_content(content: object) -> str:
    if isinstance(content, str):
        text = content.strip()
        text = re.sub(r"\s*[｜|]\s*", "\n", text)
        return text
    if not isinstance(content, list):
        return str(content or "").strip()
    paragraphs: list[str] = []
    for index, item in enumerate(content, 1):
        if not isinstance(item, dict):
            text = str(item or "").strip()
            if text:
                paragraphs.append(f"段落{index:02d}\n{text}")
            continue
        normalized = {re.sub(r"[^\w\u4e00-\u9fff]+", "", str(key)): value for key, value in item.items()}
        lines = [f"段落{index:02d}"]
        time_range = str(normalized.get("时间段", normalized.get("时间", "")) or "").strip()
        if time_range:
            lines.append(time_range)
        for label in ("画面", "动作", "台词", "旁白", "情绪"):
            value = str(normalized.get(label, "") or "").strip()
            lines.append(f"{label}：{value or '无'}")
        paragraphs.append("\n".join(lines))
    return "\n\n".join(paragraphs)


def _allocate_script_timing(content: object, target_duration: int) -> list[dict]:
    """Assign a content-aware, non-uniform, continuous timeline to script paragraphs."""
    if not isinstance(content, list):
        raise ValueError("剧本 content 必须是段落数组")
    paragraphs = [dict(item) for item in content if isinstance(item, dict)]
    if len(paragraphs) < 8:
        raise ValueError(f"剧本段落不足，至少需要8段，当前为{len(paragraphs)}段")
    if target_duration < len(paragraphs) * 2 or target_duration > len(paragraphs) * 9:
        raise ValueError(f"{len(paragraphs)}个段落无法覆盖{target_duration}秒，每段必须为2-9秒")

    def field(item: dict, name: str) -> str:
        for key, value in item.items():
            if re.sub(r"[^\w\u4e00-\u9fff]+", "", str(key)) == name:
                return str(value or "").strip()
        return ""

    weights: list[float] = []
    for index, item in enumerate(paragraphs):
        visual = field(item, "画面")
        action = field(item, "动作")
        dialogue = field(item, "台词")
        narration = field(item, "旁白")
        combined = f"{visual}{action}{dialogue}{narration}"
        weight = 1.0 + min(len(visual), 40) / 45 + min(len(action), 30) / 40
        weight += min(len(dialogue) + len(narration), 36) / 22
        if re.search(r"冲突|反转|揭露|发现|质问|争执|打|追|逃|撞|摔|抢|突然|却|但是", combined):
            weight += 0.7
        if index == len(paragraphs) - 1:
            weight += 0.8
        # Stable small variation prevents equal allocation when text lengths happen to match.
        weight += (index % 4) * 0.11
        weights.append(weight)

    durations = [2] * len(paragraphs)
    for _ in range(target_duration - sum(durations)):
        candidates = [index for index, duration in enumerate(durations) if duration < 9]
        if not candidates:
            raise ValueError("剧本时长分配超过单段9秒上限")
        selected = max(candidates, key=lambda index: (weights[index] / (durations[index] + 0.35), -index))
        durations[selected] += 1

    if len(set(durations)) < min(3, len(durations)):
        for left in range(len(durations)):
            for right in range(len(durations) - 1, -1, -1):
                if durations[left] >= 4 and durations[right] <= 7 and left != right:
                    durations[left] -= 1
                    durations[right] += 1
                    if len(set(durations)) >= min(3, len(durations)):
                        break
            if len(set(durations)) >= min(3, len(durations)):
                break

    cursor = 0
    for item, duration in zip(paragraphs, durations):
        item["时间段"] = f"{cursor}-{cursor + duration}秒"
        cursor += duration
    return paragraphs


def _validate_script_timing(content: str, target_duration: int) -> None:
    ranges = [(int(start), int(end)) for start, end in re.findall(r"(?m)^\s*(\d+)\s*[-–—‑~至]\s*(\d+)\s*秒\s*$", content)]
    if not ranges:
        raise ValueError("剧本缺少可解析的时间段")
    previous = 0
    durations: list[int] = []
    for index, (start, end) in enumerate(ranges, 1):
        if start != previous:
            raise ValueError(f"剧本段落{index}时间轴不连续")
        duration = end - start
        if duration < 2 or duration > 9:
            raise ValueError(f"剧本段落{index}时长必须为2-9秒")
        durations.append(duration)
        previous = end
    if previous != target_duration:
        raise ValueError(f"剧本总时长必须为{target_duration}秒，当前为{previous}秒")
    if len(set(durations)) < min(3, len(durations)):
        raise ValueError("剧本段落时长过于机械，必须至少使用3种不同段长")


def _validated_episode_duration(value: object) -> int:
    if isinstance(value, bool):
        raise ValueError("单集时长必须为55—65秒的整数")
    if isinstance(value, int):
        duration = value
    elif isinstance(value, str) and re.fullmatch(r"\d+", value.strip()):
        duration = int(value.strip())
    else:
        raise ValueError("单集时长必须为55—65秒的整数")
    if duration < 55 or duration > 65:
        raise ValueError("单集时长必须处于55—65秒")
    return duration


def _validate_storyboard(shots: object, target_duration: float, script: object) -> list[dict]:
    if not isinstance(shots, list):
        raise ValueError("分镜 shots 必须是数组")
    if not 15 <= len(shots) <= 23:
        raise ValueError(f"分镜数量必须为15-23个，当前为{len(shots)}个")
    required_fields = ("start_second", "end_second", "scene", "shot_size", "camera", "visual", "action", "dialogue", "sound", "image_prompt")
    previous_end = 0.0
    signatures: set[str] = set()
    normalized_dialogue: list[str] = []
    for index, shot in enumerate(shots, 1):
        if not isinstance(shot, dict):
            raise ValueError(f"镜头{index}不是有效对象")
        missing = [field for field in required_fields if field not in shot or (field != "dialogue" and not str(shot.get(field, "")).strip())]
        if missing:
            raise ValueError(f"镜头{index}缺少字段：{', '.join(missing)}")
        try:
            start, end = float(shot["start_second"]), float(shot["end_second"])
        except (TypeError, ValueError) as error:
            raise ValueError(f"镜头{index}时间不是有效数字") from error
        duration = end - start
        if abs(start - previous_end) > 0.05:
            raise ValueError(f"镜头{index}时间轴不连续：应从{previous_end:g}秒开始，实际为{start:g}秒")
        if duration < 2 or duration > 9:
            raise ValueError(f"镜头{index}时长必须为2-9秒，当前为{duration:g}秒")
        previous_end = end
        signature = _normalized_story_text(f"{shot.get('visual', '')}|{shot.get('action', '')}")
        if not signature or signature in signatures:
            raise ValueError(f"镜头{index}画面与动作重复或无效")
        signatures.add(signature)
        dialogue = _normalized_story_text(shot.get("dialogue", ""))
        characters = shot.get("characters", [])
        if not isinstance(characters, list):
            raise ValueError(f"镜头{index} characters 必须是数组")
        for character in characters:
            if not isinstance(character, dict) or not all(str(character.get(field, "")).strip() for field in ("id", "costume_id", "costume_version")):
                raise ValueError(f"镜头{index}每个出镜人物必须标注id、costume_id和costume_version")
        if dialogue and dialogue not in {"无", "无对白", "无台词"}:
            normalized_dialogue.append(dialogue)
    if abs(previous_end - float(target_duration)) > 1:
        raise ValueError(f"分镜总时长必须覆盖目标{float(target_duration):g}秒，当前为{previous_end:g}秒")
    script_dialogue = _script_dialogue_lines(script)
    if script_dialogue:
        joined = "".join(normalized_dialogue)
        missing_dialogue = [line for line in script_dialogue if line not in joined]
        if missing_dialogue:
            raise ValueError(f"分镜遗漏剧本对白{len(missing_dialogue)}句：{'；'.join(missing_dialogue[:3])}")
    return shots


def _script_segments_for_storyboard(script: object) -> list[dict]:
    """Parse the already timed script into the authoritative storyboard units.

    The script stage has already decided dialogue, action and timing.  Asking a
    large model to reproduce the entire episode as JSON is both slow and prone
    to truncation, so storyboard generation only asks the model for a compact
    directing plan and compiles these source units deterministically.
    """
    text = str(script or "")
    blocks = [block.strip() for block in re.split(r"(?=段落\d+)", text) if block.strip()]
    segments: list[dict] = []
    for block in blocks:
        time_match = re.search(r"(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)秒", block)
        if not time_match:
            continue
        item: dict[str, object] = {
            "start_second": float(time_match.group(1)),
            "end_second": float(time_match.group(2)),
        }
        for label, key in (("画面", "visual"), ("动作", "action"), ("台词", "dialogue"), ("旁白", "narration"), ("情绪", "emotion")):
            match = re.search(rf"{label}：([^\n]*)", block)
            item[key] = match.group(1).strip() if match else ""
        segments.append(item)
    return segments


def _costume_id(character_name: str, label: str = "daily") -> str:
    digest = hashlib.sha256(character_name.encode("utf-8")).hexdigest()[:8]
    return f"costume_{digest}_{_safe_name(label) or 'daily'}"


_SCENE_ACTION_PATTERN = re.compile(
    r"(?:跪(?:下|在|着)|坐(?:下|在|着)|躺(?:下|在|着)|站立|倒地|转身|回头|低头|抬头|"
    r"走(?:进|出|向|到)|跑(?:进|出|向|到)|冲(?:进|出|向)|追赶|挥(?:手|剑)|抱住|"
    r"看向|望向|哭泣|大笑|说话|喊道|进入|离开)"
)
_SCENE_PERSON_PATTERN = re.compile(r"(?:弟子|众人|人群|长老|侍卫|士兵|百姓|村民|男人|女人|男子|女子|孩童|全宗门)"
)
_SCENE_STORY_PATTERN = re.compile(
    r"(?:被(?:夺走|抢走|推进|带进|送进|关进|困在|藏进|打伤|杀死|击倒)|"
    r"(?:藏|推|冲|闯|逃|跑|走|驶|搬|抬|送|带)(?:进|入|向|到)|"
    r"失控|夺走|抢走|打斗|追逐|爆炸|起火|坍塌|倒塌|发生|后(?:藏|走|进入|来到))"
)
_SCENE_LOCATION_PATTERN = re.compile(
    r"(?:试炼场|练武场|广场|大殿|殿内|殿外|庭院|院落|房间|卧室|书房|藏经阁|阁楼|楼阁|大厅|"
    r"走廊|山门|后山|山谷|树林|街道|巷道|地牢|牢房|擂台|秘境|洞府|城门|村落|湖畔|河岸|桥上|"
    r"厨房|客厅|餐厅|饭店|卫生间|浴室|医院|诊所|病房|学校|教室|办公室|会议室|公司|商场|超市|"
    r"酒店|旅馆|车站|候车室|机场|候机厅|码头|仓库|工厂|车间|寺庙|道观|教堂|咖啡馆|图书馆|"
    r"博物馆|体育馆|停车场|公园|花园|游乐园|电影院|剧院|舞台|摄影棚|实验室|工作室|店铺|"
    r"住宅|公寓|别墅|宿舍|天台|屋顶|地下室|电梯间|楼梯间|大厅|前台|操场|球场|海滩|沙漠|草原|雪原)$"
)


def _is_reusable_empty_scene_name(value: object, character_names: list[str] | tuple[str, ...] = ()) -> bool:
    """A scene asset is a reusable place, never a character action or state sentence."""
    name = str(value or "").strip()
    if not name or not _SCENE_LOCATION_PATTERN.search(name) or _SCENE_ACTION_PATTERN.search(name) or _SCENE_PERSON_PATTERN.search(name) or _SCENE_STORY_PATTERN.search(name):
        return False
    return not any(character and character in name for character in character_names)


def _project_character_names(body: dict) -> list[str]:
    """Read the authoritative character roster for an exact project scope."""
    project_id = str(body.get("project_id") or "").strip()
    tenant_id = str(body.get("tenant_id") or "").strip()
    user_id = str(body.get("user_id") or "").strip()
    if not project_id or not tenant_id or not user_id:
        return []
    with PROJECT_STORE_LOCK:
        project = next((item for item in _load_store().get("projects", []) if (
            str(item.get("id") or "") == project_id
            and str(item.get("tenant_id") or "") == tenant_id
            and str(item.get("user_id") or "") == user_id
        )), None)
    if not project:
        return []
    stages = project.get("stage_state", {}) if isinstance(project.get("stage_state"), dict) else {}
    names: list[str] = []
    for stage_name in ("assets", "outline"):
        stage = stages.get(stage_name, {}) if isinstance(stages.get(stage_name), dict) else {}
        data = stage.get("data", {}) if isinstance(stage.get("data"), dict) else {}
        if stage_name == "outline" and isinstance(data.get("plan"), dict):
            data = data["plan"]
        items = data.get("characters", []) if isinstance(data.get("characters"), list) else []
        for item in items:
            name = str(item.get("name") or "").strip() if isinstance(item, dict) else ""
            if name and name not in names:
                names.append(name)
    return names


def _normalize_empty_scene_assets(items: object, character_names: list[str] | tuple[str, ...] = ()) -> list[dict]:
    normalized: list[dict] = []
    for raw in items if isinstance(items, list) else []:
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name") or "").strip()
        if not _is_reusable_empty_scene_name(name, character_names):
            continue
        item = dict(raw)
        location = str(item.get("location") or name).strip()
        layout = str(item.get("layout") or "").strip()
        lighting = str(item.get("lighting") or "").strip()
        fixed = "、".join(str(value).strip() for value in item.get("fixed_elements", []) if str(value).strip())
        item["location"] = location
        item["image_prompt"] = "，".join(value for value in (location, layout, lighting, fixed) if value) + "，45度空场景全景，纯环境与建筑，无人物、无人形、无人体、无文字"
        item["status"] = str(item.get("status") or "pending")
        normalized.append(item)
    return normalized


def _scene_location_from_text(value: object) -> str:
    text = str(value or "")
    background = re.search(r"(?:背景(?:是|为)|地点(?:在|是|为|[:：]))([^，。；]{2,24})", text)
    candidates = [background.group(1)] if background else []
    candidates.extend(re.findall(
        r"[\u4e00-\u9fff]{0,10}(?:试炼场|练武场|广场|大殿|殿内|殿外|庭院|院落|房间|卧室|书房|藏经阁|阁楼|楼阁|大厅|走廊|山门|后山|山谷|树林|街道|巷道|地牢|牢房|擂台|秘境|洞府|城门|村落|湖畔|河岸|桥上|厨房|客厅|餐厅|饭店|卫生间|浴室|医院|诊所|病房|学校|教室|办公室|会议室|公司|商场|超市|酒店|旅馆|车站|候车室|机场|候机厅|码头|仓库|工厂|车间|寺庙|道观|教堂|咖啡馆|图书馆|博物馆|体育馆|停车场|公园|花园|游乐园|电影院|剧院|舞台|摄影棚|实验室|工作室|店铺|住宅|公寓|别墅|宿舍|天台|屋顶|地下室|电梯间|楼梯间|前台|操场|球场|海滩|沙漠|草原|雪原)",
        text,
    ))
    for candidate in candidates:
        cleaned = re.sub(r"^(?:一座|一处|古色古香的|宏伟的|昏暗的|宽阔的|空旷的|远处的)+", "", candidate).strip()
        if _is_reusable_empty_scene_name(cleaned):
            return cleaned[:20]
    return ""


def _costume_label_from_text(text: str) -> str:
    patterns = (
        ("战斗服", "battle"), ("战甲", "battle"), ("礼服", "formal"), ("华服", "formal"),
        ("练功服", "training"), ("制服", "uniform"), ("长袍", "robe"), ("衣袍", "robe"),
        ("披风", "cloak"), ("斗篷", "cloak"), ("日常服", "daily"), ("常服", "daily"),
    )
    return next((label for token, label in patterns if token in text), "")


def _costume_changes_for_shot(text: str, character_names: list[str]) -> dict[str, str]:
    changes: dict[str, str] = {}
    verb_pattern = re.compile(r"换上|换成|换下|穿上|穿着|披上|脱下|撕掉|露出")
    last_actors: list[str] = []
    for clause in re.split(r"[，,。；;！!？?]", text):
        clause_mentions = sorted(((clause.rfind(name), name) for name in character_names if name in clause), reverse=True)
        if clause_mentions:
            nearest = clause_mentions[0][1]
            last_actors = [nearest]
            for _, candidate in clause_mentions[1:]:
                if f"{candidate}与{nearest}" in clause or f"{candidate}和{nearest}" in clause or f"{nearest}与{candidate}" in clause or f"{nearest}和{candidate}" in clause:
                    last_actors.append(candidate)
        verbs = list(verb_pattern.finditer(clause))
        if not verbs:
            continue
        prefix = clause[:verbs[0].start()]
        mentioned = sorted(((prefix.rfind(name), name) for name in character_names if name in prefix), reverse=True)
        if mentioned:
            actor_names = [mentioned[0][1]]
            last_actor = actor_names[0]
            for _, candidate in mentioned[1:]:
                if f"{candidate}与{last_actor}" in prefix or f"{candidate}和{last_actor}" in prefix or f"{last_actor}与{candidate}" in prefix or f"{last_actor}和{candidate}" in prefix:
                    actor_names.append(candidate)
            last_actors = actor_names
        elif last_actors:
            actor_names = list(last_actors)
        else:
            continue
        for verb_index, verb in enumerate(verbs):
            if verb.group() in {"脱下", "撕掉", "换下"}:
                continue
            segment_end = verbs[verb_index + 1].start() if verb_index + 1 < len(verbs) else len(clause)
            label = _costume_label_from_text(clause[verb.end():segment_end])
            if label:
                for actor in actor_names:
                    changes[actor] = label
    return changes


def _compile_storyboard_from_script(script: object, episode: int, style: str, direction: dict, characters: object = None) -> list[dict]:
    segments = _script_segments_for_storyboard(script)
    if not 15 <= len(segments) <= 23:
        raise ValueError(f"剧本必须包含15-23个带时间段落才能编译分镜，当前为{len(segments)}个")
    camera_rules = [str(value).strip() for value in direction.get("camera_rules", []) if str(value).strip()]
    if not camera_rules:
        camera_rules = ["极慢推进", "微平移", "小幅推镜", "微动定格"]
    palette = str(direction.get("palette") or style or "统一电影画面")[:24]
    lighting = str(direction.get("lighting") or "固定柔和主光")[:24]
    shot_sizes = ("全景", "中景", "近景", "特写")
    character_names = [str(item.get("name") or "").strip() for item in (characters or []) if isinstance(item, dict) and str(item.get("name") or "").strip()]
    active_costumes = {name: "daily" for name in character_names}
    active_scene = "剧情场景"
    shots: list[dict] = []
    for index, segment in enumerate(segments, 1):
        visual = str(segment.get("visual") or "")
        action = str(segment.get("action") or "")
        dialogue = str(segment.get("dialogue") or "")
        narration = str(segment.get("narration") or "")
        if not dialogue or dialogue in {"（无）", "无"}:
            dialogue = narration if narration not in {"", "（无）", "无"} else "无"
        elif narration not in {"", "（无）", "无"}:
            dialogue = f"{dialogue}；旁白：{narration}"
        detected_scene = _scene_location_from_text(f"{visual}，{action}")
        if detected_scene:
            active_scene = detected_scene
        scene = active_scene
        shot_size = shot_sizes[min(3, ((index - 1) * 4) // max(1, len(segments)))]
        camera = camera_rules[(index - 1) % len(camera_rules)][:16]
        prompt = f"{style}，{palette}，{lighting}，{shot_size}，{visual}，{action}"[:90]
        visible_characters: list[dict] = []
        shot_text = f"{visual}{action}{dialogue}"
        costume_changes = _costume_changes_for_shot(shot_text, character_names)
        for name in character_names:
            if name not in shot_text:
                continue
            explicit_label = costume_changes.get(name, "")
            explicit_change = bool(explicit_label)
            previous_label = active_costumes[name]
            if explicit_change:
                active_costumes[name] = explicit_label
            current_label = active_costumes[name]
            visible_characters.append({
                "id": name,
                "costume_id": _costume_id(name, current_label),
                "costume_version": "v1",
                "action": action[:35],
                "change_type": "change" if current_label != previous_label else ("initial" if index == 1 else "continue"),
            })
        shots.append({
            "episode": episode,
            "shot_number": index,
            "start_second": segment["start_second"],
            "end_second": segment["end_second"],
            "scene": scene,
            "shot_size": shot_size,
            "camera": camera,
            "visual": visual[:45],
            "action": action[:35],
            "dialogue": dialogue,
            "sound": "同期声与后期音效"[:16],
            "emotion": str(segment.get("emotion") or "自然")[:8],
            "image_prompt": prompt,
            "shot_type": "action",
            "characters": visible_characters,
        })
    return shots


def _memory_limits() -> tuple[int, int, int]:
    """Return total, available and mandatory OS reserve bytes on macOS/Linux/Windows."""
    try:
        import psutil  # type: ignore[import-not-found]
        memory = psutil.virtual_memory()
        total, available = int(memory.total), int(memory.available)
    except ImportError:
        if sys.platform == "darwin":
            total = int(subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True).strip())
            vm_stat = subprocess.check_output(["vm_stat"], text=True)
            page_size = int(re.search(r"page size of (\d+) bytes", vm_stat).group(1))
            pages = {name:int(value.replace(".", "")) for name, value in re.findall(r"Pages (free|inactive|speculative|purgeable):\s+([\d.]+)", vm_stat)}
            available = sum(pages.values()) * page_size
            pressure = subprocess.run(["memory_pressure", "-Q"], capture_output=True, text=True, timeout=10, check=False)
            free_match = re.search(r"System-wide memory free percentage:\s*(\d+)%", pressure.stdout)
            if free_match:
                available = max(available, int(total * int(free_match.group(1)) / 100))
        elif os.name == "posix":
            page_size = int(os.sysconf("SC_PAGE_SIZE")); total = int(os.sysconf("SC_PHYS_PAGES")) * page_size; available = int(os.sysconf("SC_AVPHYS_PAGES")) * page_size
        else:
            total = available = 8 * GIB
    reserve = max(8 * GIB, int(total * 0.25), total - available + 4 * GIB)
    if sys.platform == "darwin" and total >= 120 * GIB: reserve = max(reserve, 35 * GIB)
    return total, available, reserve


def _require_memory(estimated_bytes: int) -> None:
    total, available, reserve = _memory_limits()
    strict_mac = sys.platform == "darwin" and total >= 120 * GIB
    ai_cap = min(total - reserve, 90 * GIB) if strict_mac else total - reserve
    runtime_floor = 35 * GIB if strict_mac else max(4 * GIB, int(total * 0.05))
    if estimated_bytes > ai_cap or available - estimated_bytes < runtime_floor:
        raise RuntimeError(f"内存保护已阻止任务：预计需要 {estimated_bytes / GIB:.0f}GB，必须为系统保留 {reserve / GIB:.0f}GB；任务需拆分后串行执行")


def _memory_ready(estimated_bytes: int) -> tuple[bool, dict]:
    total, available, reserve = _memory_limits()
    strict_mac = sys.platform == "darwin" and total >= 120 * GIB
    ai_cap = min(total - reserve, 90 * GIB) if strict_mac else total - reserve
    runtime_floor = 35 * GIB if strict_mac else max(4 * GIB, int(total * 0.05))
    ready = estimated_bytes <= ai_cap and available - estimated_bytes >= runtime_floor
    return ready, {
        "available_gb": round(available / GIB, 1),
        "required_gb": round(estimated_bytes / GIB, 1),
        "reserve_gb": round(max(reserve, runtime_floor) / GIB, 1),
        "checked_at": datetime.now(UTC).isoformat(),
    }


def _wait_for_post_comfy_memory(
    estimated_bytes: int,
    *,
    job_id: str | None = None,
    timeout_seconds: float = 60.0,
) -> None:
    """Wait only for the bounded asynchronous release window after Comfy /free."""
    ready, memory = _memory_ready(estimated_bytes)
    if ready:
        return
    recent_release = LAST_COMFY_FREE_AT > 0 and time.monotonic() - LAST_COMFY_FREE_AT <= 120
    if not recent_release:
        try:
            with urlopen(f"{COMFY_API}/queue", timeout=10) as response:
                queue = json.loads(response.read())
            comfy_idle = not queue.get("queue_running") and not queue.get("queue_pending")
        except Exception:
            comfy_idle = False
        if comfy_idle:
            _free_comfy_memory()
            recent_release = LAST_COMFY_FREE_AT > 0 and time.monotonic() - LAST_COMFY_FREE_AT <= 120
    if not recent_release:
        _require_memory(estimated_bytes)
        return
    deadline = time.monotonic() + max(1.0, timeout_seconds)
    if job_id:
        _update_image_job(job_id, status="waiting_memory", phase="waiting_memory", memory=memory, heartbeat_at=_iso_now())
    while time.monotonic() < deadline:
        if job_id:
            _assert_image_job_runnable(job_id)
        time.sleep(1)
        ready, memory = _memory_ready(estimated_bytes)
        if ready:
            if job_id:
                _update_image_job(job_id, status="processing", phase="memory_ready", memory=memory, heartbeat_at=_iso_now())
            return
        if job_id:
            _update_image_job(job_id, memory=memory, heartbeat_at=_iso_now())
    raise RuntimeError(
        "内存保护等待Comfy释放超时："
        f"可用{memory['available_gb']}GB，需要{memory['required_gb']}GB，必须保留{memory['reserve_gb']}GB"
    )


def _load_store() -> dict:
    if not PROJECTS_FILE.exists():
        return {"version": 1, "projects": []}
    try:
        store = json.loads(PROJECTS_FILE.read_text(encoding="utf-8"))
        if not isinstance(store, dict) or not isinstance(store.get("projects", []), list):
            raise ValueError("invalid project store")
        return store
    except (OSError, ValueError, json.JSONDecodeError):
        snapshots = sorted(PROJECT_SNAPSHOTS_DIR.glob("*.json"), reverse=True) if PROJECT_SNAPSHOTS_DIR.is_dir() else []
        for snapshot in snapshots:
            try:
                recovered = json.loads(snapshot.read_text(encoding="utf-8"))
                if isinstance(recovered, dict) and isinstance(recovered.get("projects", []), list):
                    return recovered
            except (OSError, ValueError, json.JSONDecodeError):
                continue
        raise RuntimeError("项目数据损坏且没有有效快照")


def _save_store(store: dict) -> None:
    with PROJECT_STORE_LOCK:
        PROJECTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        if PROJECTS_FILE.is_file():
            PROJECT_SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
            snapshot = PROJECT_SNAPSHOTS_DIR / f"{time.time_ns()}-{uuid4().hex}.json"
            shutil.copy2(PROJECTS_FILE, snapshot)
            for expired in sorted(PROJECT_SNAPSHOTS_DIR.glob("*.json"), reverse=True)[50:]:
                expired.unlink(missing_ok=True)
        atomic_write_json(PROJECTS_FILE, store, prefix="projects-")


def _create_project_version(project: dict, stage: object, reason: object) -> dict:
    PROJECT_VERSIONS_DIR.mkdir(parents=True, exist_ok=True)
    version_id = f"{time.time_ns()}-{uuid4().hex}"
    record = {
        "version_id": version_id, "project_id": project.get("id"), "project_name": project.get("name", ""),
        "stage": str(stage or "manual"), "reason": str(reason or ""), "created_at": _iso_now(),
        "media_count": 0, "project": project,
    }
    target = PROJECT_VERSIONS_DIR / f"{version_id}.json"
    atomic_write_json(target, record, prefix="project-version-")
    return {key:value for key, value in record.items() if key != "project"}


def _read_project_version(version_id: object) -> dict | None:
    value = str(version_id or "")
    if not re.fullmatch(r"[0-9]+-[0-9a-f]{32}", value):
        return None
    target = PROJECT_VERSIONS_DIR / f"{value}.json"
    try: return json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError): return None


def _sanitize_asset_media_projection(data: dict) -> dict:
    """Reject stale local media URLs before they can become authoritative project state."""
    def available(value: object) -> bool:
        url = str(value or "").strip()
        if not url or not url.startswith("/api/result-media?"):
            return bool(url)
        try:
            _local_media_path(url)
            return True
        except FileNotFoundError:
            return False

    for key in ("characters", "scenes", "props"):
        for item in data.get(key, []) if isinstance(data.get(key), list) else []:
            if not isinstance(item, dict):
                continue
            if item.get("image_url") and not available(item.get("image_url")):
                item["image_url"] = None
                item["clothing_reference_url"] = None
                item["baseline_confirmed_at"] = None
                item["confirmation_phase"] = None
                item["status"] = "pending"
                item["error"] = ""
            item["detail_image_urls"] = [url for url in item.get("detail_image_urls", []) if available(url)]
            for variant in item.get("detail_assets", []) if isinstance(item.get("detail_assets"), list) else []:
                if not isinstance(variant, dict) or not variant.get("image_url") or available(variant.get("image_url")):
                    continue
                variant["image_url"] = None
                variant["status"] = "pending"
                variant["error"] = ""
    return data


def _write_project_stage(
    project_id: str,
    tenant_id: str,
    user_id: str,
    stage_name: str,
    incoming_data: dict,
    *,
    stage_generation: int = 0,
    projection_only: bool = False,
) -> dict:
    """Merge one stage against the latest on-disk project while holding the full transaction lock."""
    raw_status = str(incoming_data.get("status") or "completed")
    lifecycle = {
        "idle":"idle", "pending":"queued", "queued":"queued", "generating":"running", "running":"running",
        "auditing":"running", "repairing":"running", "rechecking":"running", "waiting_confirmation":"pending_confirmation",
        "pending_confirmation":"pending_confirmation", "confirmed":"completed", "completed":"completed", "pass":"completed",
        "paused":"paused", "stopped":"paused", "failed":"failed", "error":"failed", "stale":"stale",
        "skipped":"skipped", "cancelled":"cancelled",
    }.get(raw_status, "queued")
    if stage_name in {"outline", "script", "storyboard"} and lifecycle in {"pending_confirmation", "completed"}:
        violations = STORY_BIBLE.validate(STORY_BIBLE._episodes(stage_name, incoming_data))
        if violations: raise StoryBibleError("；".join(violations))
    identity = {"tenant_id":tenant_id, "user_id":user_id, "project_id":project_id}
    authoritative_state = _production_orchestrator().state(identity) if projection_only else {}
    authoritative_event = (authoritative_state.get("stage_events") or {}).get(canonical_stage(stage_name), {})
    authoritative_generation = int(authoritative_event.get("stage_generation") or 0)
    protected_lifecycle = str(authoritative_event.get("lifecycle") or "")
    with PROJECT_STORE_LOCK:
        store = _load_store()
        project = next((item for item in store.get("projects", []) if item.get("id") == project_id and item.get("tenant_id") == tenant_id and item.get("user_id") == user_id), None)
        if not project:
            raise LookupError("project_not_found")
        current_stage = project.setdefault("stage_state", {}).get(stage_name, {})
        current_data = current_stage.get("data", {}) if isinstance(current_stage, dict) else {}
        if (
            projection_only
            and authoritative_generation > 0
            and protected_lifecycle in {"pending_confirmation", "completed", "failed", "cancelled"}
            and lifecycle in {"idle", "queued", "running"}
        ):
            # Public project-state writes are UI projections, not production
            # authority. A snapshot captured before the fenced server commit
            # must not move the visible stage back to a no-owner running state.
            incoming_data = {
                **incoming_data,
                "status":current_data.get("status") or protected_lifecycle,
                "error":current_data.get("error") or str(authoritative_event.get("error") or ""),
            }
            raw_status = str(incoming_data["status"])
            lifecycle = {
                "waiting_confirmation":"pending_confirmation", "pending_confirmation":"pending_confirmation",
                "confirmed":"completed", "completed":"completed", "failed":"failed", "cancelled":"cancelled",
            }.get(raw_status, protected_lifecycle)
            if stage_name == "assets":
                # Preserve the complete fenced census while accepting media
                # progress from an older UI snapshot. The normal asset merge
                # keeps current-only profiles and their generated media.
                incoming_data["_merge_existing"] = True
            else:
                incoming_data = dict(current_data)
        if stage_name == "assets" and incoming_data.pop("_merge_existing", False):
            authoritative_asset_success = raw_status in {"waiting_confirmation", "confirmed", "completed"}
            def merge_profiles(key: str) -> list[dict]:
                existing = [dict(item) for item in current_data.get(key, []) if isinstance(item, dict)]
                by_name = {re.sub(r"\s+", "", str(item.get("name") or "")).lower():item for item in existing}
                merged: list[dict] = []
                for candidate in incoming_data.get(key, []):
                    if not isinstance(candidate, dict): continue
                    normalized = re.sub(r"\s+", "", str(candidate.get("name") or "")).lower()
                    old = by_name.pop(normalized, None)
                    if old:
                        value = {**old, **candidate}
                        for field in ("status", "image_url", "error", "detail_assets", "confirmation_phase", "baseline_confirmed_at", "model3d_status", "model3d_result", "model3d_job_id"):
                            if field in old: value[field] = old[field]
                        if authoritative_asset_success and str(value.get("error") or "").strip() == "production stage is already running: assets":
                            value["status"] = "waiting_confirmation" if value.get("image_url") else "pending"
                            value["error"] = ""
                    else:
                        value = {**candidate, "status":"pending", "generation_nonce":str(uuid4())}
                    merged.append(value)
                return [*merged, *by_name.values()]
            incoming_data = {
                **current_data, **incoming_data,
                "characters":merge_profiles("characters"), "scenes":merge_profiles("scenes"), "props":merge_profiles("props"),
                "source_episodes":sorted(set([*(current_data.get("source_episodes") or []), *(incoming_data.get("source_episodes") or [])])),
            }
        if stage_name == "assets" and int(current_data.get("census_version", 0) or 0) >= 2 and int(incoming_data.get("census_version", 0) or 0) < 2:
            raise ValueError("stale_asset_census")
        if stage_name == "assets":
            incoming_data = _sanitize_asset_media_projection(incoming_data)
        stamp = _iso_now(); revision = int(current_stage.get("revision", 0) or 0) + 1 if isinstance(current_stage, dict) else 1
        stage = {
            "data": incoming_data,
            "updated_at": stamp,
            "revision":revision,
            "authority_generation":stage_generation or int(current_stage.get("authority_generation", 0) or 0),
        }
        project["stage_state"][stage_name] = stage; project["updated_at"] = stamp
        _save_store(store)
        PROJECT_STAGE_CONDITION.notify_all()
    fingerprint = hashlib.sha256(json.dumps(incoming_data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    if projection_only:
        return {**stage, "workflow":authoritative_state}
    record = PRODUCTION_LEDGER.upsert({
        **identity, "stage":stage_name, "scope_type":"project", "scope_id":"all", "lifecycle":lifecycle,
        "stage_substate":raw_status, "content_fingerprint":fingerprint, "checkpoint":f"revision:{revision}",
        "progress":{"completed":1 if lifecycle == "completed" else 0, "total":1}, "error":str(incoming_data.get("error") or ""),
    })
    story_bible = None
    if stage_name in {"outline", "script", "storyboard"} and lifecycle in {"pending_confirmation", "completed"}:
        story_bible = STORY_BIBLE.update(identity, stage_name, incoming_data)
    confirmation = None
    if lifecycle == "completed":
        record = PRODUCTION_LEDGER.confirm({**identity, "stage":record["stage"], "scope_type":"project", "scope_id":"all"})
        confirmation = record["confirmation"]
    workflow = _production_orchestrator().report(
        identity, record["stage"], lifecycle, revision=revision, content_fingerprint=fingerprint,
        story_bible=story_bible, confirmation=confirmation, stage_generation=stage_generation,
        projection_revision=revision if stage_generation else 0,
    )
    return {**stage, "workflow":workflow}


def _write_storyboard_stream_progress(body: dict, shots: list[dict], episode: int, cancel_event: threading.Event) -> None:
    project_id = str(body.get("project_id") or (body.get("context") or {}).get("project_id") or "").strip()
    tenant_id = str(body.get("tenant_id") or (body.get("context") or {}).get("tenant_id") or "").strip()
    user_id = str(body.get("user_id") or (body.get("context") or {}).get("user_id") or "").strip()
    if not project_id or not tenant_id or not user_id:
        return
    with PROJECT_STORE_LOCK:
        if cancel_event.is_set():
            raise RuntimeError("storyboard generation stopped")
        _write_project_stage(project_id, tenant_id, user_id, "storyboard", {
            "shots": shots, "status":"generating", "error":"", "audits":[], "streaming_episode":episode,
        })


def _mark_storyboard_stopped(body: dict) -> bool:
    project_id = str(body.get("project_id") or "").strip()
    tenant_id = str(body.get("tenant_id") or "local-default").strip()
    user_id = str(body.get("user_id") or "aoo").strip()
    if not project_id:
        return False
    with PROJECT_STORE_LOCK:
        store = _load_store()
        project = next((item for item in store.get("projects", []) if item.get("id") == project_id and item.get("tenant_id") == tenant_id and item.get("user_id") == user_id), None)
        if not project:
            return False
        current = project.get("stage_state", {}).get("storyboard", {})
        data = dict(current.get("data") or {}) if isinstance(current, dict) else {}
        data.update(status="failed", error="已停止生成，可从未完成集数继续")
        _write_project_stage(project_id, tenant_id, user_id, "storyboard", data)
    return True


def _load_assistant() -> dict:
    if not ASSISTANT_FILE.exists():
        return {"conversations": {}, "display_history": {}, "key_memories": {}, "sessions": {}, "drafts": {}}
    return json.loads(ASSISTANT_FILE.read_text(encoding="utf-8"))


def _save_assistant(store: dict) -> None:
    atomic_write_json(ASSISTANT_FILE, store, prefix="assistant-")


def _load_agent_jobs() -> dict:
    if not AGENT_JOBS_FILE.exists():
        return {"jobs": {}}
    try:
        return json.loads(AGENT_JOBS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"jobs": {}}


def _save_agent_jobs(store: dict) -> None:
    atomic_write_json(AGENT_JOBS_FILE, store, prefix="system-agent-jobs-")


def _load_text_jobs() -> dict:
    if not TEXT_JOBS_FILE.exists():
        return _merge_durable_tasks("text", TEXT_JOBS_FILE, {"jobs": {}})
    try:
        payload = json.loads(TEXT_JOBS_FILE.read_text(encoding="utf-8"))
        return _merge_durable_tasks("text", TEXT_JOBS_FILE, payload if isinstance(payload.get("jobs"), dict) else {"jobs": {}})
    except (OSError, ValueError, json.JSONDecodeError):
        return _merge_durable_tasks("text", TEXT_JOBS_FILE, {"jobs": {}})


def _save_text_jobs(store: dict) -> None:
    _sync_durable_tasks("text", TEXT_JOBS_FILE, store)
    atomic_write_json(TEXT_JOBS_FILE, store, prefix="text-generation-jobs-")


def _update_text_job(text_job_id: str, **changes: object) -> dict:
    with TEXT_JOB_LOCK:
        store = _load_text_jobs(); job = store.setdefault("jobs", {}).setdefault(text_job_id, {})
        job.update(changes); job["updated_at"] = _iso_now(); _save_text_jobs(store)
        return dict(job)


def _finish_text_job(job_id: str, status: str, error: str = "") -> None:
    with TEXT_JOB_LOCK:
        current = _load_text_jobs().get("jobs", {}).get(job_id, {})
        if current.get("status") in {"failed", "completed"} and current.get("status") != status:
            active = ACTIVE_TEXT_JOBS.pop(job_id, None) or {}
            heartbeat_stop = active.get("heartbeat_stop")
            if isinstance(heartbeat_stop, threading.Event): heartbeat_stop.set()
            return
        _update_text_job(job_id, status=status, error=error, finished_at=_iso_now(), heartbeat_at=_iso_now())
        active = ACTIVE_TEXT_JOBS.pop(job_id, None) or {}
        heartbeat_stop = active.get("heartbeat_stop")
        if isinstance(heartbeat_stop, threading.Event): heartbeat_stop.set()


def _begin_text_job(body: dict, stage: str, phase: str, timeout_seconds: int, endpoint: str = "") -> tuple[str, str]:
    """Register every blocking narrative request against its actual worker thread."""
    project_id = str(body.get("project_id") or body.get("current_project") or "")
    client_generation_id = str(body.get("generation_id") or body.get("client_generation_id") or "")
    job_id = str(uuid4())
    now = time.time()
    heartbeat_stop = threading.Event()
    with TEXT_JOB_LOCK:
        conflict = next((active_id for active_id, active in ACTIVE_TEXT_JOBS.items()
            if active.get("project_id") == project_id and active.get("stage") == stage), "")
        if conflict:
            return "", conflict
        ACTIVE_TEXT_JOBS[job_id] = {
            "project_id":project_id, "stage":stage, "phase":phase,
            "started_epoch":now, "heartbeat_epoch":now,
            "worker_thread":threading.current_thread(), "thread_id":threading.current_thread().ident,
            "heartbeat_stop":heartbeat_stop,
        }
        _update_text_job(job_id, job_id=job_id, client_generation_id=client_generation_id,
            project_id=project_id, stage=stage, phase=phase, status="generating",
            timeout_seconds=timeout_seconds, started_at=_iso_now(), heartbeat_at=_iso_now(),
            endpoint=endpoint, request=dict(body))
    def heartbeat() -> None:
        while not heartbeat_stop.wait(5):
            with TEXT_JOB_LOCK:
                active = ACTIVE_TEXT_JOBS.get(job_id)
                if not active: return
                active["heartbeat_epoch"] = time.time()
                _update_text_job(job_id, heartbeat_at=_iso_now())
    threading.Thread(target=heartbeat, daemon=True, name=f"text-heartbeat-{job_id[:8]}").start()
    return job_id, ""


def _text_job_stopped(job_id: str) -> bool:
    with TEXT_JOB_LOCK:
        return _load_text_jobs().get("jobs", {}).get(job_id, {}).get("status") == "failed"


def _replay_persisted_request(endpoint: str, payload: dict) -> None:
    """Replay an exact persisted command through the same public boundary."""
    try:
        port = int(os.environ.get("SHORT_DRAMA_PORT", "8787"))
        request = Request(f"http://127.0.0.1:{port}{endpoint}", data=json.dumps(payload, ensure_ascii=False).encode("utf-8"), headers={"Content-Type":"application/json"}, method="POST")
        with urlopen(request, timeout=30) as response: response.read()
    except Exception:
        return


def _formal_model_owner() -> str:
    with FORMAL_MODEL_OWNER_LOCK:
        return FORMAL_MODEL_OWNER_JOB_ID


def _recover_text_jobs() -> None:
    with TEXT_JOB_LOCK:
        store = _load_text_jobs(); changed = False
        for job in store.get("jobs", {}).values():
            if job.get("status") in {"queued", "generating", "retrying", "processing"}:
                job.update(status="failed", error="服务重启，剧本任务已回收", finished_at=_iso_now(), updated_at=_iso_now()); changed = True
        if changed: _save_text_jobs(store)
        for active in ACTIVE_TEXT_JOBS.values():
            heartbeat_stop = active.get("heartbeat_stop")
            if isinstance(heartbeat_stop, threading.Event): heartbeat_stop.set()
        ACTIVE_TEXT_JOBS.clear()
    with PROJECT_STORE_LOCK:
        projects = _load_store(); changed = False
        for project in projects.get("projects", []):
            for stage_name, label in (("outline", "大纲"), ("script", "剧本")):
                stage = project.get("stage_state", {}).get(stage_name, {})
                data = stage.get("data", {}) if isinstance(stage, dict) else {}
                if data.get("status") != "generating": continue
                data.update(status="failed", phase="", error=f"服务重启，{label}任务已回收；可继续生成", generation_id="", generation_started_at=0, heartbeat_at=0)
                stage["updated_at"] = _iso_now(); stage["revision"] = int(stage.get("revision", 0) or 0) + 1; changed = True
        if changed: _save_store(projects)


def _monitor_text_jobs() -> None:
    while not TEXT_WATCHDOG_STOP.wait(TEXT_WATCHDOG_SECONDS):
        now = time.time()
        expired: list[tuple[str, bool]] = []
        with TEXT_JOB_LOCK:
            store = _load_text_jobs()
            for job_id, job in list(store.get("jobs", {}).items()):
                if job.get("status") not in {"queued", "generating", "retrying", "processing"}: continue
                active = ACTIVE_TEXT_JOBS.get(job_id)
                heartbeat = float(active.get("heartbeat_epoch", 0)) if active else 0
                started = float(active.get("started_epoch", 0)) if active else 0
                worker = active.get("worker_thread") if active else None
                worker_alive = isinstance(worker, threading.Thread) and worker.is_alive() and worker.ident == active.get("thread_id")
                timeout_seconds = float(job.get("timeout_seconds") or TEXT_JOB_TIMEOUT_SECONDS)
                if not active or not worker_alive or now - heartbeat > timeout_seconds or now - started > timeout_seconds:
                    expired.append((job_id, job.get("stage") in {"outline", "script", "storyboard"}))
        for job_id, requires_formal_stop in expired:
            owner = _formal_model_owner()
            terminated = not requires_formal_stop or owner != job_id or _terminate_ollama_model(TEXT_FORMAL_MODEL)
            with TEXT_JOB_LOCK:
                store = _load_text_jobs(); job = store.get("jobs", {}).get(job_id, {})
                if job.get("status") not in {"queued", "generating", "retrying", "processing"}: continue
                if not terminated:
                    job.update(status="processing", error="模型终止尚未确认，看门狗将继续回收", updated_at=_iso_now())
                    _save_text_jobs(store); continue
                job.update(status="failed", error="文本任务无活动进程或心跳超时，已由看门狗回收", finished_at=_iso_now(), updated_at=_iso_now())
                removed = ACTIVE_TEXT_JOBS.pop(job_id, None) or {}
                heartbeat_stop = removed.get("heartbeat_stop")
                if isinstance(heartbeat_stop, threading.Event): heartbeat_stop.set()
                _save_text_jobs(store)


def _conversation_key(context: dict) -> str:
    return ":".join(str(context.get(key, "")) for key in ("tenant_id", "user_id", "current_project", "session_id"))


def _ollama_json_local(
    prompt: str,
    model: str = TEXT_LIGHT_MODEL,
    estimated_memory: int = TEXT_LIGHT_ESTIMATED_MEMORY,
    *,
    release_model: bool = True,
    keep_alive: int = 0,
    timeout_seconds: int = 600,
    owner_job_id: str = "",
    num_ctx: int = 8192,
    num_predict: int = 2048,
) -> dict:
    global FORMAL_MODEL_OWNER_JOB_ID
    with _claim_production_resource("text", owner_job_id or f"text-{uuid4()}", timeout=1800):
        if owner_job_id and _text_job_stopped(owner_job_id):
            raise RuntimeError("文本任务已停止，禁止启动模型推理")
        _require_memory(estimated_memory)
        if owner_job_id:
            with FORMAL_MODEL_OWNER_LOCK:
                FORMAL_MODEL_OWNER_JOB_ID = owner_job_id
        completed = False
        request = Request(
            "http://127.0.0.1:11434/api/generate",
            data=json.dumps({"model": model, "prompt": prompt, "format": "json", "stream": False, "think": False, "keep_alive": keep_alive, "options": {"num_ctx": num_ctx, "num_predict":num_predict, "num_batch": 128}}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310 - fixed loopback endpoint
                payload = json.loads(response.read())
                completed = True
        finally:
            if release_model or not completed:
                _unload_ollama_model(model)
            if owner_job_id:
                with FORMAL_MODEL_OWNER_LOCK:
                    if FORMAL_MODEL_OWNER_JOB_ID == owner_job_id:
                        FORMAL_MODEL_OWNER_JOB_ID = ""
    # Qwen3-VL through some Ollama builds may place valid structured output in
    # `thinking` even when think=false. Prefer the normal response, but accept
    # that provider-specific field so the production chain does not fail after
    # a successful inference.
    structured_text = str(payload.get("response") or "").strip() or str(payload.get("thinking") or "").strip()
    if structured_text.startswith("```json"):
        structured_text = structured_text[7:]
    if structured_text.startswith("```"):
        structured_text = structured_text[3:]
    if structured_text.endswith("```"):
        structured_text = structured_text[:-3]
    if not structured_text.strip():
        raise ValueError(f"{model}未返回结构化JSON")
    return json.loads(structured_text.strip())


def _unload_ollama_model(model: str | None = None) -> None:
    for target in ([model] if model else [TEXT_LIGHT_MODEL, TEXT_FORMAL_MODEL, TEXT_AUDIT_MODEL]):
        request = Request(
            "http://127.0.0.1:11434/api/generate",
            data=json.dumps({"model":target, "prompt":"", "stream":False, "keep_alive":0}).encode("utf-8"),
            headers={"Content-Type":"application/json"}, method="POST",
        )
        try:
            with urlopen(request, timeout=15) as response:  # noqa: S310 - fixed loopback endpoint
                response.read()
        except Exception:
            pass


def _ollama_model_loaded(model: str) -> bool:
    try:
        request = Request("http://127.0.0.1:11434/api/ps", method="GET")
        with urlopen(request, timeout=5) as response:  # noqa: S310 - fixed loopback endpoint
            payload = json.loads(response.read())
        return any(str(item.get("name") or item.get("model")) == model for item in payload.get("models", []))
    except Exception:
        return True


def _terminate_ollama_model(model: str) -> bool:
    """Stop the actual Ollama runner so a timed-out request cannot outlive its job."""
    try:
        result = subprocess.run(["/usr/local/bin/ollama", "stop", model], capture_output=True, text=True, timeout=30, check=False)
        if result.returncode != 0:
            _unload_ollama_model(model)
    except (OSError, subprocess.SubprocessError):
        _unload_ollama_model(model)
    for _ in range(10):
        if not _ollama_model_loaded(model): return True
        time.sleep(0.2)
    _unload_ollama_model(model)
    for _ in range(10):
        if not _ollama_model_loaded(model): return True
        time.sleep(0.2)
    return False


def _mlx_json(prompt: str) -> dict:
    """Run one isolated MXFP4 audit and release all MLX weights when it exits."""
    if not MLX_VLM_PYTHON.is_file():
        raise RuntimeError(f"Qwen3.5 122B MLX 运行环境不存在：{MLX_VLM_PYTHON}")
    if not (TEXT_AUDIT_MODEL_PATH / "config.json").is_file():
        raise RuntimeError(f"Qwen3.5 122B MXFP4 模型不存在：{TEXT_AUDIT_MODEL_PATH}")
    with _claim_production_resource("audit", f"audit-{uuid4()}", timeout=1800):
        _unload_ollama_model()
        _require_memory(TEXT_AUDIT_ESTIMATED_MEMORY)
        process = subprocess.run(
            [str(MLX_VLM_PYTHON), str(MLX_JSON_WORKER), "--model", str(TEXT_AUDIT_MODEL_PATH)],
            input=json.dumps({"prompt": prompt, "max_tokens": 768}, ensure_ascii=False),
            capture_output=True,
            text=True,
            timeout=900,
            check=False,
        )
    if process.returncode != 0:
        detail = process.stderr.strip().splitlines()[-1] if process.stderr.strip() else "未知错误"
        raise RuntimeError(f"Qwen3.5 122B MXFP4 推理失败：{detail}")
    try:
        result = json.loads(process.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError("Qwen3.5 122B MXFP4 未返回结构化 JSON") from error
    if not isinstance(result, dict):
        raise RuntimeError("Qwen3.5 122B MXFP4 结果不是 JSON 对象")
    return result


def _global_director_decision(context: dict) -> dict:
    """Use the 122B model only for exceptional global routing decisions."""
    prompt = f"""你是AI短剧全局总导演，只负责失败后的流程路由，不生成正文。
当前生产上下文：{json.dumps(context, ensure_ascii=False, sort_keys=True)}
只能返回JSON：{{"action":"repair|manual|cancel","stage":"当前或上游规范阶段","reason":"简短中文证据"}}。
普通可局部修复问题必须repair；缺少人工审美或版权判断时manual；不可恢复且继续会污染下游时cancel。
禁止跳过人工确认，禁止把失败标为完成。"""
    return _mlx_json(prompt)


def _production_orchestrator() -> ProductionOrchestrator:
    global PRODUCTION_ORCHESTRATOR
    with PRODUCTION_ORCHESTRATOR_LOCK:
        if PRODUCTION_ORCHESTRATOR is None:
            director = _global_director_decision if NARRATIVE_MODEL_REVIEW_ENABLED else None
            PRODUCTION_ORCHESTRATOR = PRODUCTION_EXTENSIONS.create("checkpoint.langgraph", database=PRODUCTION_ORCHESTRATOR_FILE, director=director)
        return PRODUCTION_ORCHESTRATOR


def _narrative_audit(body: dict) -> dict:
    stage = str(body.get("stage", "")).strip()
    if stage not in {"outline", "script", "storyboard"}:
        raise ValueError("审核阶段必须是 outline、script 或 storyboard")
    mode = str(body.get("audit_mode", "both")).strip()
    phase = "final" if mode == "final" else "initial"
    content = json.dumps(body.get("content", {}), ensure_ascii=False)
    if len(content) > 120_000:
        raise ValueError("待审核文本超过本地审核上下文上限，请按批次提交")
    prior = json.dumps(body.get("prior_audit", {}), ensure_ascii=False)
    prompt = f"""你是AI短剧{stage}质量审核员。严格依据规范审核，不改写正文，只输出JSON。
必须执行的规范：
{_production_spec_for(stage)}

审核阶段：{phase}
审核范围：{body.get('range', '')}
项目要求：{json.dumps(body.get('project_requirements', {}), ensure_ascii=False)}
上游上下文：{json.dumps(body.get('upstream_context', {}), ensure_ascii=False)}
待审核内容：{content}
初审记录：{prior}
逐项检查剧情连续性、角色设定、时长节奏、台词唯一性、镜头完整性及规范硬门禁。
对大纲和剧本必须额外逐集检查：核心事件语义重复、冲突流程模板化、反派手段循环、女主被动等待救援、男主或盟友工具人化、配角动机无推进、能力升级无明确新能力或代价、剧名卖点未形成具体场面、结尾钩子空泛、标题语义重合。
任意一项存在时必须判定 needs_fix，并准确列出受影响集数；禁止以措辞不同为由放过语义重复。
仅输出：{{"status":"pass或needs_fix","summary":"审核结论","issues":[{{"location":"准确位置","description":"问题","suggestion":"可执行修复要求"}}]}}
没有实质问题时status必须为pass且issues必须为空；存在问题时status必须为needs_fix且issues不得为空。"""
    result = _ollama_json(prompt, TEXT_AUDIT_MODEL, TEXT_AUDIT_ESTIMATED_MEMORY, timeout_seconds=1800, num_ctx=32768)
    status = str(result.get("status", "")).strip()
    issues = result.get("issues", [])
    if status not in {"pass", "needs_fix"} or not isinstance(issues, list):
        raise ValueError("审核模型返回结构无效")
    normalized_issues = []
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        normalized_issues.append({
            "location": str(issue.get("location", "全文")).strip() or "全文",
            "description": str(issue.get("description", "")).strip(),
            "suggestion": str(issue.get("suggestion", "")).strip(),
        })
    if status == "needs_fix" and not normalized_issues:
        raise ValueError("审核模型判定需修复但未提供问题")
    return {
        "status": status,
        "summary": str(result.get("summary", "审核通过" if status == "pass" else "审核未通过")).strip(),
        "issues": normalized_issues,
        "phase": phase,
        "model": TEXT_AUDIT_MODEL,
    }


def _narrative_repair(body: dict) -> dict:
    stage = str(body.get("stage", "")).strip()
    if stage not in {"outline", "script", "storyboard"}:
        raise ValueError("修正阶段必须是 outline、script 或 storyboard")
    content = body.get("content")
    if not isinstance(content, dict):
        raise ValueError("待修正内容必须是对象")
    prompt = f"""你是AI短剧{stage}主编。根据审核问题自动修正文稿，只修问题，不改变已通过设定，只输出JSON。
必须执行的规范：
{_production_spec_for(stage)}

项目要求：{json.dumps(body.get('project_requirements', {}), ensure_ascii=False)}
上游上下文：{json.dumps(body.get('upstream_context', {}), ensure_ascii=False)}
原始内容：{json.dumps(content, ensure_ascii=False)}
审核问题：{json.dumps(body.get('issues', []), ensure_ascii=False)}
返回格式严格为：{{"content":修正后的完整原结构对象,"repair_summary":"修正摘要"}}。禁止只返回差异，禁止省略未修改字段。"""
    result = _ollama_json(prompt, TEXT_AUDIT_MODEL, TEXT_AUDIT_ESTIMATED_MEMORY, timeout_seconds=1800, num_ctx=32768)
    repaired = result.get("content")
    if not isinstance(repaired, dict) or not repaired:
        raise ValueError("72B修正模型未返回完整内容")
    return {"content":repaired, "repair_summary":str(result.get("repair_summary") or "已按审核问题自动修正"), "model":TEXT_AUDIT_MODEL}


def _audit_and_repair_narrative(stage: str, body: dict, content: dict) -> tuple[dict, list[dict]]:
    _checkpoint_production_stage(body, stage)
    collection_key = {"outline":"episodes", "script":"scripts", "storyboard":"shots"}[stage]
    items = content.get(collection_key)
    if not body.get("_chunked") and isinstance(items, list) and len(json.dumps(content, ensure_ascii=False)) > 9_000:
        chunks: list[list[dict]] = []; current: list[dict] = []
        for item in items:
            candidate = [*current, item]
            candidate_content = {**content, collection_key:candidate}
            if current and len(json.dumps(candidate_content, ensure_ascii=False)) > 9_000:
                chunks.append(current); current = [item]
            else: current = candidate
        if current: chunks.append(current)
        combined: list[dict] = []; audits: list[dict] = []
        for index, chunk in enumerate(chunks, 1):
            _checkpoint_production_stage(body, stage)
            revised, chunk_audits = _audit_and_repair_narrative(stage, {**body, "_chunked":True, "range":f"{body.get('range', '全剧')}·批次{index}/{len(chunks)}"}, {**content, collection_key:chunk})
            _checkpoint_production_stage(body, stage)
            combined.extend(revised[collection_key]); audits.extend(chunk_audits)
        return {**content, collection_key:combined}, audits
    # Stage cancellation is process-local control state.  Keep it available to
    # checkpoints, but never expose the Event through provider/remote payloads.
    audit_body = {**{key:value for key, value in body.items() if key != "_cancel_event"}, "stage":stage, "audit_mode":"initial", "content":content}
    _checkpoint_production_stage(body, stage)
    initial = _invoke_production_capability("audit.narrative", body=audit_body)
    _checkpoint_production_stage(body, stage)
    if initial.get("status") == "pass":
        return content, [initial]
    repaired = _invoke_production_capability("text.narrative.repair", body={**audit_body, "issues":initial.get("issues", [])})
    _checkpoint_production_stage(body, stage)
    final_content = repaired["content"]
    original_items = content.get(collection_key); repaired_items = final_content.get(collection_key)
    if not isinstance(original_items, list) or not isinstance(repaired_items, list) or len(repaired_items) != len(original_items):
        raise ValueError(f"{stage}自动修正改变了条目数量")
    if stage == "outline" and not isinstance(final_content.get("plan"), dict):
        raise ValueError("大纲自动修正缺少完整总纲")
    identity_key = "episode" if stage != "storyboard" else "shot_number"
    if [item.get(identity_key) for item in repaired_items if isinstance(item, dict)] != [item.get(identity_key) for item in original_items if isinstance(item, dict)]:
        raise ValueError(f"{stage}自动修正改变了条目标识或顺序")
    _checkpoint_production_stage(body, stage)
    final = _invoke_production_capability("audit.narrative", body={**audit_body, "audit_mode":"final", "content":final_content, "prior_audit":initial})
    _checkpoint_production_stage(body, stage)
    if final.get("status") != "pass":
        raise RuntimeError(str(final.get("summary") or f"{stage}自动修正后终审未通过"))
    return final_content, [initial, final]


def _shutdown_text_jobs() -> None:
    with TEXT_JOB_LOCK:
        store = _load_text_jobs()
        for job_id, job in store.get("jobs", {}).items():
            if job.get("status") in {"queued", "generating", "retrying", "processing"}:
                job.update(status="failed", error="服务关闭，剧本任务已回收", finished_at=_iso_now(), updated_at=_iso_now())
        _save_text_jobs(store)
        for active in ACTIVE_TEXT_JOBS.values():
            heartbeat_stop = active.get("heartbeat_stop")
            if isinstance(heartbeat_stop, threading.Event): heartbeat_stop.set()
        ACTIVE_TEXT_JOBS.clear()
    with PROJECT_STORE_LOCK:
        projects = _load_store(); changed = False
        for project in projects.get("projects", []):
            for stage_name, label in (("outline", "大纲"), ("script", "剧本")):
                stage = project.get("stage_state", {}).get(stage_name, {})
                data = stage.get("data", {}) if isinstance(stage, dict) else {}
                if data.get("status") != "generating": continue
                data.update(status="failed", phase="", error=f"服务关闭，{label}任务已回收；可继续生成", generation_id="", generation_started_at=0, heartbeat_at=0)
                stage["updated_at"] = _iso_now(); stage["revision"] = int(stage.get("revision", 0) or 0) + 1; changed = True
        if changed: _save_store(projects)
    _unload_ollama_model()


def _ollama_vision(images: list[str], prompt: str) -> str:
    clean_images: list[str] = []
    with tempfile.TemporaryDirectory(prefix="short-drama-vision-") as temporary:
        for index, image in enumerate(images[:4]):
            encoded = image.split(",", 1)[1] if image.startswith("data:") and "," in image else image
            try:
                source = Path(temporary) / f"source-{index}.png"
                resized = Path(temporary) / f"resized-{index}.jpg"
                source.write_bytes(base64.b64decode(encoded, validate=True))
                subprocess.run(["sips", "-Z", "768", "-s", "format", "jpeg", str(source), "--out", str(resized)], check=True, capture_output=True, timeout=30)
                clean_images.append(base64.b64encode(resized.read_bytes()).decode("ascii"))
            except Exception:
                clean_images.append(encoded)
    if not clean_images:
        raise ValueError("没有可识别的图片帧")
    user_instruction = (prompt or "请识别人物、场景、动作、文字和关键细节。").strip()
    reverse_prompt = any(token in user_instruction for token in ("反推", "提示词", "画风分析"))
    if reverse_prompt:
        vision_prompt = """请直接观察图片，并用简体中文逐项描述图片中真实可见的内容：人物或物体、年龄与性别、五官与发型、服装与配饰、姿态与动作、景别与构图、镜头视角、背景、光线、颜色、画风、材质和清晰度。必须写具体画面内容，不要解释能力，不要道歉，不要输出空泛字段名，不要虚构看不见的内容。"""
    else:
        vision_prompt = f"""你是截图和视觉证据提取器。请仔细查看全部图片。
必须先逐行抄录清晰可见的中文、英文、数字、文件名和错误码，再描述画面事实。
不得猜测图片之外的原因，不得给泛化模板答案，不得遗漏与用户问题有关的文字。
用户要求：{user_instruction}
只输出视觉证据和能够从画面直接确认的事实。"""
    with _claim_production_resource("audit", f"vision-{uuid4()}", timeout=900):
        _require_memory(12 * GIB)
        request = Request(
            "http://127.0.0.1:11434/api/generate",
            data=json.dumps({"model":"llava:latest", "prompt":vision_prompt, "images":clean_images, "stream":False, "keep_alive":0, "options":{"num_ctx":4096}}).encode("utf-8"),
            headers={"Content-Type":"application/json"}, method="POST",
        )
        with urlopen(request, timeout=600) as response:  # noqa: S310 - fixed loopback endpoint
            payload = json.loads(response.read())
    evidence = str(payload.get("response", "")).strip()
    if not evidence:
        raise RuntimeError("视觉模型未返回识别结果")
    if reverse_prompt:
        reversed_prompt = _ollama_json(f"""你是专业中文生图提示词反推器。只能依据下方视觉证据整理提示词。
每一项必须写出画面中真实可见的具体内容；禁止输出“主体、年龄性别、五官发型、服装配饰、姿态动作、景别构图、镜头视角、背景环境、光线、色彩、画风媒介、材质细节、画质词”等字段名或占位模板。证据没有提到的细节不要虚构。
输出严格JSON：{{"prompt":"用连续中文短语描述画面的具体内容","negative_prompt":"根据这张画面给出具体的排除内容"}}
视觉证据：{evidence}""")
        positive = str(reversed_prompt.get("prompt", "")).strip()
        negative = str(reversed_prompt.get("negative_prompt", "")).strip()
        placeholder_terms = ("主体；年龄性别", "五官发型；服装配饰", "姿态动作；景别构图", "画风媒介；材质细节")
        if not positive or any(term in positive for term in placeholder_terms):
            positive = evidence
        if not negative or "与画面冲突的主体" in negative:
            negative = "低清晰度，模糊，畸形肢体，多余手指，错误透视，重复主体，文字，水印，标志"
        return f"正向提示词：{positive}\n负面提示词：{negative}"
    calibrated = _ollama_json(f"""你是中文多模态结果校准器。根据视觉模型提供的画面证据，直接回答用户对附件的要求。
硬性规则：
1. 全部使用简体中文；图片内原有英文、文件名和错误码可以原样保留。
2. 只依据视觉证据回答，禁止编造图片中不存在的内容、原因或建议。
3. 若用户在问截图里的具体问题，直接给针对性结论；若证据不足，明确写“图片中无法确认”。
4. 不要复述“可能有多种原因”之类的泛化模板，不要用英文展开回答。
5. 输出严格 JSON：{{"description":"最终中文回答"}}

用户要求：{user_instruction}
视觉证据：{evidence}""")
    description = str(calibrated.get("description", "")).strip()
    if not description:
        raise RuntimeError("视觉校准未返回结果")
    return description


def _prop_contains_live_person(image: dict) -> bool:
    """Reject live people in prop assets while allowing sculptures and figurines."""
    source = _local_media_path(image.get("url"))
    encoded = base64.b64encode(source.read_bytes()).decode("ascii")
    request = Request(
        "http://127.0.0.1:11434/api/generate",
        data=json.dumps({
            "model":"llava:latest",
            "prompt":(
                "这是道具资产合规检测。只要画面出现任何写实人类形象、真人照片、写实人脸、真实人体、真人手脚、"
                "真人背影、真人剪影、真人倒影、镜中人、海报人像或屏幕人像，都判定为违规；即使无法确认现实中是否为活人，"
                "只要视觉上是写实人类形象也必须判定违规。雕像、雕塑、人偶、玩偶本身允许，不算违规。"
                "先用一句话描述画面主体并明确是否看见写实人脸或人体，即使人物出现在照片、屏幕或界面中也必须写出；"
                "最后一行必须二选一写 PERSON_DEPICTION 或 NO_PERSON_DEPICTION。"
            ),
            "images":[encoded], "stream":False, "keep_alive":0,
            "options":{"num_ctx":1024, "num_predict":96, "temperature":0, "seed":7},
        }).encode("utf-8"),
        headers={"Content-Type":"application/json"}, method="POST",
    )
    with _claim_production_resource("audit", f"prop-person-{uuid4()}", timeout=900):
        _require_memory(12 * GIB)
        with urlopen(request, timeout=600) as response: payload = json.loads(response.read())
    answer = str(payload.get("response", "")).strip().upper()
    if "NO_PERSON_DEPICTION" in answer: return False
    if "PERSON_DEPICTION" in answer: return True
    verdict = next((line.strip() for line in reversed(answer.splitlines()) if line.strip()), "")
    evidence = answer.removesuffix(verdict) if verdict in {"PERSON_DEPICTION", "NO_PERSON_DEPICTION"} else answer
    human_terms = ("PERSON", "MAN ", "WOMAN", "INDIVIDUAL", "HUMAN", "FACE", "BODY", "人物", "男人", "女人", "一个人", "人脸", "人体", "身体", "头部")
    allowed_terms = ("STATUE", "SCULPTURE", "FIGURINE", "DOLL", "雕像", "雕塑", "人偶", "玩偶")
    return any(term in evidence for term in human_terms) and not any(term in evidence for term in allowed_terms)


def _run_image_validation(
    job_id: str,
    phase: str,
    validator,
    image: dict,
    *,
    timeout_seconds: float = IMAGE_VALIDATION_TIMEOUT_SECONDS,
    heartbeat_seconds: float = 2.0,
) -> tuple[bool, str]:
    """Keep post-generation validation inside the durable image-job lifecycle."""
    completed = threading.Event()
    outcome: dict[str, object] = {}

    def validate() -> None:
        try:
            outcome["result"] = validator(image)
        except Exception as error:
            outcome["error"] = error
        finally:
            completed.set()

    _assert_image_job_runnable(job_id)
    _update_image_job(job_id, status="processing", phase=phase, heartbeat_at=_iso_now(), pid=None, process_group=None)
    threading.Thread(target=validate, daemon=True, name=f"image-validation-{job_id[:8]}").start()
    deadline = time.monotonic() + timeout_seconds
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            _cancel_image_validation_work(job_id)
            completed.wait(5)
            raise RuntimeError(f"图片后验收超时（{int(timeout_seconds)}秒）：{phase}")
        if completed.wait(min(heartbeat_seconds, remaining)):
            break
        try:
            _assert_image_job_runnable(job_id)
        except Exception:
            _cancel_image_validation_work(job_id)
            completed.wait(5)
            raise
        _update_image_job(job_id, status="processing", phase=phase, heartbeat_at=_iso_now(), pid=None, process_group=None)
    _assert_image_job_runnable(job_id)
    validation_error = outcome.get("error")
    if isinstance(validation_error, Exception):
        raise validation_error
    result = outcome.get("result")
    if not isinstance(result, tuple) or len(result) != 2:
        raise RuntimeError(f"图片后验收返回无效结果：{phase}")
    return bool(result[0]), str(result[1])


def _cancel_image_validation_work(job_id: str) -> None:
    """Cancel every owned validation resource before the image job reaches a terminal state."""
    RESOURCE_SCHEDULER.cancel_job(job_id)
    with IMAGE_JOB_LOCK:
        process = ACTIVE_IMAGE_PROCESSES.get(job_id)
        job = _load_image_jobs().get("jobs", {}).get(job_id, {})
    if process is not None:
        _terminate_process_tree(process)
    _cancel_job_comfy_prompts(job)
    _terminate_ollama_model("llava:latest")


def _image_job_identity(job_id: str) -> dict[str, str]:
    """Recover explicit scope because validation workers do not inherit request thread-local state."""
    if not job_id:
        return {}
    with IMAGE_JOB_LOCK:
        job = _load_image_jobs().get("jobs", {}).get(job_id, {})
    request = job.get("request") if isinstance(job.get("request"), dict) else {}
    return _production_identity({
        key: job.get(key) or request.get(key)
        for key in ("tenant_id", "user_id", "project_id")
    })


def _validate_prop_asset(image: dict, *, job_id: str = "") -> tuple[bool, str]:
    """Require a single isolated prop instead of merely checking that people are absent."""
    source = _local_media_path(image.get("url"))
    request = Request(
        "http://127.0.0.1:11434/api/generate",
        data=json.dumps({
            "model":"llava:latest",
            "prompt":(
                "这是道具资产硬验收。画面必须是单个独立可拿取道具的摄影棚产品图，不得是建筑、房间、街道、商店、自然景观或完整场景。"
                "返回严格JSON布尔值：{\"exactly_one_isolated_prop\":...,\"plain_neutral_background\":...,"
                "\"no_scene_or_environment\":...,\"no_text_or_signage\":...,\"no_live_person_or_body_part\":...}。"
                "只要出现店铺、门窗、道路、家具、多人、真人手脚、招牌、海报或大段文字，对应项必须判false。不要解释。"
            ),
            "images":[base64.b64encode(source.read_bytes()).decode("ascii")],
            "stream":False,"keep_alive":0,"format":"json",
            "options":{"num_ctx":1536,"num_predict":120,"temperature":0,"seed":29},
        }).encode("utf-8"),
        headers={"Content-Type":"application/json"}, method="POST",
    )
    with _claim_production_resource(
        "audit", job_id or f"prop-audit-{uuid4()}", timeout=IMAGE_VALIDATION_TIMEOUT_SECONDS,
    ):
        _require_memory(12 * GIB)
        with urlopen(request, timeout=IMAGE_VALIDATION_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read())
    evidence = str(payload.get("response", "")).strip()
    try:
        verdict = json.loads(evidence)
    except json.JSONDecodeError:
        return False, evidence[:500] or "道具视觉模型未返回结构化结果"
    required = ("exactly_one_isolated_prop", "plain_neutral_background", "no_scene_or_environment", "no_text_or_signage", "no_live_person_or_body_part")
    return all(verdict.get(key) is True for key in required), json.dumps(verdict, ensure_ascii=False)


def _validate_scene_asset(image: dict, *, job_id: str = "") -> tuple[bool, str]:
    """Reject people and model-invented glyphs before optional exact text overlay."""
    source = _local_media_path(image.get("url"))
    request = Request(
        "http://127.0.0.1:11434/api/generate",
        data=json.dumps({
            "model":"llava:latest",
            "prompt":(
                "这是空场景资产硬验收。返回严格JSON布尔值："
                '{"is_environment_or_architecture":...,"no_person_or_human_figure":...,"no_text_letters_numbers_or_signage":...}。'
                "只要画面出现真人、人体、背影、剪影、雕像人形、海报人物或屏幕人物，no_person_or_human_figure必须为false；"
                "只要出现任何汉字、乱码、字母、数字、标题、标牌、招牌、水印或类似字形，no_text_letters_numbers_or_signage必须为false。不要解释。"
            ),
            "images":[base64.b64encode(source.read_bytes()).decode("ascii")],
            "stream":False,"keep_alive":0,"format":"json",
            "options":{"num_ctx":1536,"num_predict":120,"temperature":0,"seed":37},
        }).encode("utf-8"),
        headers={"Content-Type":"application/json"}, method="POST",
    )
    with _claim_production_resource(
        "audit", job_id or f"scene-audit-{uuid4()}", timeout=IMAGE_VALIDATION_TIMEOUT_SECONDS,
    ):
        _require_memory(12 * GIB)
        with urlopen(request, timeout=IMAGE_VALIDATION_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read())
    evidence = str(payload.get("response", "")).strip()
    try:
        verdict = json.loads(evidence)
    except json.JSONDecodeError:
        return False, evidence[:500] or "场景视觉模型未返回结构化结果"
    required = ("is_environment_or_architecture", "no_person_or_human_figure", "no_text_letters_numbers_or_signage")
    return all(verdict.get(key) is True for key in required), json.dumps(verdict, ensure_ascii=False)


def _validation_remaining(job_id: str, deadline: float | None, maximum: float) -> float:
    if job_id:
        _assert_image_job_runnable(job_id)
    if deadline is None:
        return maximum
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise RuntimeError("人物图片后验收已超时")
    return min(maximum, remaining)


def _run_image_validation_subprocess(
    command: list[str], *, job_id: str = "", deadline: float | None = None, maximum: float,
) -> str:
    """Run one deterministic validator as an owned, cancellable image-job subprocess."""
    _validation_remaining(job_id, deadline, maximum)
    process = subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True,
    )
    if job_id:
        with IMAGE_JOB_LOCK:
            ACTIVE_IMAGE_PROCESSES[job_id] = process
        _update_image_job(job_id, pid=process.pid, process_group=process.pid, heartbeat_at=_iso_now())
    try:
        while process.poll() is None:
            try:
                _validation_remaining(job_id, deadline, maximum)
            except Exception:
                _terminate_process_tree(process)
                raise
            time.sleep(0.2)
        stdout, stderr = process.communicate()
        if process.returncode != 0:
            raise RuntimeError((stderr or stdout or "人物确定性验收子进程失败").strip()[-2000:])
        if job_id:
            _assert_image_job_runnable(job_id)
        return stdout
    finally:
        if process.poll() is None:
            _terminate_process_tree(process)
        if job_id:
            with IMAGE_JOB_LOCK:
                if ACTIVE_IMAGE_PROCESSES.get(job_id) is process:
                    ACTIVE_IMAGE_PROCESSES.pop(job_id, None)


def _face_pose_angles(
    image_path: Path, *, job_id: str = "", deadline: float | None = None,
) -> tuple[float, float, float] | None:
    """Return InsightFace pitch/yaw/roll so orientation gates do not rely on VLM judgment alone."""
    script = """import json,sys,cv2
from insightface.app import FaceAnalysis
app=FaceAnalysis(name='buffalo_l',root=sys.argv[2],providers=['CPUExecutionProvider'])
app.prepare(ctx_id=-1,det_size=(640,640))
faces=app.get(cv2.imread(sys.argv[1]))
if not faces: print('null')
else:
 face=max(faces,key=lambda item:float((item.bbox[2]-item.bbox[0])*(item.bbox[3]-item.bbox[1])))
 print(json.dumps([float(value) for value in face.pose]))
"""
    stdout = _run_image_validation_subprocess(
        [str(COMFY_PYTHON), "-c", script, str(image_path), "/Users/aoo/AI/Models/Vision/InsightFace"],
        job_id=job_id, deadline=deadline, maximum=120,
    )
    payload = json.loads(stdout.strip().splitlines()[-1])
    return tuple(payload) if isinstance(payload, list) and len(payload) == 3 else None


def _mirror_character_candidate_for_target(candidate: Path, target_pose: str) -> bool:
    """Correct a pure left/right semantic inversion without regenerating identity or clothing."""
    pose = _face_pose_angles(candidate, job_id=job_id, deadline=deadline)
    if pose is None:
        return False
    yaw = float(pose[1])
    inverted = (target_pose == "left_45_full" and -60.0 <= yaw <= -30.0) or (
        target_pose == "right_45_full" and 30.0 <= yaw <= 60.0
    )
    if not inverted:
        return False
    script = "import cv2,sys; p=sys.argv[1]; im=cv2.imread(p); assert im is not None; assert cv2.imwrite(p,cv2.flip(im,1))"
    subprocess.run([str(COMFY_PYTHON), "-c", script, str(candidate)], check=True, capture_output=True, text=True, timeout=60)
    return True


def _face_embedding_similarity(
    reference: Path, candidate: Path, *, job_id: str = "", deadline: float | None = None,
) -> float | None:
    """Return normalized InsightFace embedding similarity for machine admission."""
    script = r'''import json,sys,cv2,numpy as np
from insightface.app import FaceAnalysis
app=FaceAnalysis(name="buffalo_l",root=sys.argv[3],providers=["CPUExecutionProvider"])
app.prepare(ctx_id=-1,det_size=(640,640))
vectors=[]
for path in sys.argv[1:3]:
    faces=app.get(cv2.imread(path))
    if not faces: print("null"); raise SystemExit(0)
    face=max(faces,key=lambda item:float((item.bbox[2]-item.bbox[0])*(item.bbox[3]-item.bbox[1])))
    vector=np.asarray(face.normed_embedding,dtype=np.float32)
    vectors.append(vector/max(float(np.linalg.norm(vector)),1e-8))
print(json.dumps(float(np.dot(vectors[0],vectors[1]))))
'''
    stdout = _run_image_validation_subprocess(
        [str(COMFY_PYTHON), "-c", script, str(reference), str(candidate), "/Users/aoo/AI/Models/Vision/InsightFace"],
        job_id=job_id, deadline=deadline, maximum=180,
    )
    payload = json.loads(stdout.strip().splitlines()[-1])
    return float(payload) if isinstance(payload, (int, float)) else None


def _prepare_ipadapter_reference_crops(face_source: Path, clothing_source: Path, face_target: Path, clothing_target: Path) -> None:
    """Separate face geometry and garment pixels before the two IP-Adapters."""
    script = r'''import cv2,sys,numpy as np
from insightface.app import FaceAnalysis
from ultralytics import YOLO
face_source,clothing_source,face_target,clothing_target,models=sys.argv[1:]
app=FaceAnalysis(name="buffalo_l",root=models,providers=["CPUExecutionProvider"])
app.prepare(ctx_id=-1,det_size=(640,640))
face_image=cv2.imread(face_source)
faces=app.get(face_image)
if not faces: raise RuntimeError("face_reference_not_found")
face=max(faces,key=lambda item:float((item.bbox[2]-item.bbox[0])*(item.bbox[3]-item.bbox[1])))
x1,y1,x2,y2=map(float,face.bbox); face_h=y2-y1; side=max(x2-x1,face_h)*2.15; cx=(x1+x2)/2; cy=(y1+y2)/2+face_h*0.22
left=int(cx-side/2); top=int(cy-side/2); right=int(cx+side/2); bottom=int(cy+side/2)
pad_l=max(0,-left); pad_t=max(0,-top); pad_r=max(0,right-face_image.shape[1]); pad_b=max(0,bottom-face_image.shape[0])
if pad_l or pad_t or pad_r or pad_b:
    face_image=cv2.copyMakeBorder(face_image,pad_t,pad_b,pad_l,pad_r,cv2.BORDER_CONSTANT,value=(128,128,128))
    left+=pad_l; right+=pad_l; top+=pad_t; bottom+=pad_t
face_crop=face_image[top:bottom,left:right]
cv2.imwrite(face_target,face_crop,[cv2.IMWRITE_PNG_COMPRESSION,3])
cloth=cv2.imread(clothing_source); h,w=cloth.shape[:2]
result=YOLO("/Users/aoo/AI/ComfyUI-Shared/models/yolo11n.pt")(clothing_source,verbose=False)[0]
people=[]
for cls,conf,box in zip(result.boxes.cls,result.boxes.conf,result.boxes.xyxy):
    if int(cls)==0 and float(conf)>=0.25: people.append((float(conf),*[float(v) for v in box]))
if not people: raise RuntimeError("clothing_person_not_found")
_,px1,py1,px2,py2=max(people,key=lambda item:item[0])
output=np.full_like(cloth,128)
head_cut=int(min(py2,py1+(py2-py1)*0.23))
person_width=max(1.0,px2-px1)
ix1=max(0,int(px1+person_width*0.18)); ix2=min(w,int(px2-person_width*0.18)); iy2=min(h,int(py2))
output[head_cut:iy2,ix1:ix2]=cloth[head_cut:iy2,ix1:ix2]
cv2.imwrite(clothing_target,output,[cv2.IMWRITE_PNG_COMPRESSION,3])
'''
    subprocess.run(
        [str(COMFY_PYTHON), "-c", script, str(face_source), str(clothing_source), str(face_target), str(clothing_target), "/Users/aoo/AI/Models/Vision/InsightFace"],
        check=True, capture_output=True, text=True, timeout=240,
    )


def _write_ipadapter_attention_masks(face_target: Path, clothing_target: Path, width: int, height: int) -> None:
    """Write target-space regional masks so identity and garment adapters cannot repaint each other."""
    def write_mask(target: Path, top: float, bottom: float, left: float, right: float) -> None:
        pixels = bytearray(width * height)
        x1, x2 = int(width * left), int(width * right)
        y1, y2 = int(height * top), int(height * bottom)
        for y in range(max(0, y1), min(height, y2)):
            offset = y * width
            pixels[offset + max(0, x1):offset + min(width, x2)] = bytes([255]) * max(0, min(width, x2) - max(0, x1))
        target.write_bytes(f"P5\n{width} {height}\n255\n".encode() + pixels)
    write_mask(face_target, 0.02, 0.25, 0.27, 0.73)
    write_mask(clothing_target, 0.17, 0.91, 0.18, 0.82)


def _pose_proportion_metrics(
    candidate: Path, *, job_id: str = "", deadline: float | None = None,
) -> dict[str, float] | None:
    """Measure body segments from OpenPose coordinates instead of VLM estimates."""
    input_name = f"short_drama_pose_metrics/{uuid4().hex}{candidate.suffix.lower()}"
    input_path = COMFY_INPUT / input_name
    input_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(candidate, input_path)
    prefix = f"short_drama_pose_metrics/{uuid4().hex}"
    graph = {
        "1":{"class_type":"LoadImage","inputs":{"image":input_name}},
        "2":{"class_type":"OpenposePreprocessor","inputs":{"image":["1",0],"detect_hand":"enable","detect_body":"enable","detect_face":"disable","resolution":768,"scale_stick_for_xinsr_cn":"enable"}},
        "3":{"class_type":"SavePoseKpsAsJsonFile","inputs":{"pose_kps":["2",1],"filename_prefix":prefix}},
    }
    prompt_id = ""
    prompt_finished = False
    try:
        request_timeout = max(0.1, _validation_remaining(job_id, deadline, 30))
        request = Request(f"{COMFY_API}/prompt", data=json.dumps({"prompt":graph}).encode(), headers={"Content-Type":"application/json"}, method="POST")
        with urlopen(request, timeout=request_timeout) as response: prompt_id = json.loads(response.read())["prompt_id"]
        _validation_remaining(job_id, deadline, 300)
        if job_id:
            _update_image_job(job_id, validation_prompt_id=prompt_id, heartbeat_at=_iso_now())
        poll_deadline = time.monotonic() + _validation_remaining(job_id, deadline, 300)
        while time.monotonic() < poll_deadline:
            _validation_remaining(job_id, deadline, 300)
            time.sleep(1)
            history_timeout = max(0.1, _validation_remaining(job_id, deadline, 30))
            with urlopen(f"{COMFY_API}/history/{prompt_id}", timeout=history_timeout) as response: history = json.loads(response.read())
            if prompt_id not in history: continue
            record = history[prompt_id]
            prompt_finished = True
            if record.get("status", {}).get("status_str") != "success": return None
            break
        if not prompt_finished:
            raise RuntimeError("人物OpenPose比例验收超时")
        matches = sorted(COMFY_OUTPUT.glob(f"{prefix}_*.json"), key=lambda path:path.stat().st_mtime, reverse=True)
        if not matches: return None
        payload = json.loads(matches[0].read_text(encoding="utf-8"))[0]
        people = payload.get("people", [])
        if len(people) != 1: return None
        points = people[0].get("pose_keypoints_2d", [])
        if len(points) < 42: return None
        def xy(index: int) -> tuple[float, float] | None:
            offset = index * 3
            if float(points[offset + 2]) <= 0: return None
            return float(points[offset]), float(points[offset + 1])
        def distance(left: int, right: int) -> float | None:
            a, b = xy(left), xy(right)
            return math.hypot(a[0]-b[0], a[1]-b[1]) if a and b else None
        def paired(a: tuple[int,int], b: tuple[int,int]) -> tuple[float,float] | None:
            first = [distance(*a), distance(*b)]
            values = [value for value in first if value is not None]
            return (sum(values)/len(values), len(values)) if values else None
        upper = paired((2,3),(5,6)); lower = paired((3,4),(6,7))
        thigh = paired((8,9),(11,12)); calf = paired((9,10),(12,13))
        shoulders = [point for point in (xy(2),xy(5)) if point]; hips = [point for point in (xy(8),xy(11)) if point]; ankles = [point for point in (xy(10),xy(13)) if point]
        if not all((upper,lower,thigh,calf,shoulders,hips,ankles)): return None
        shoulder_y=sum(point[1] for point in shoulders)/len(shoulders); hip_y=sum(point[1] for point in hips)/len(hips); ankle_y=sum(point[1] for point in ankles)/len(ankles)
        arm_difference=abs(upper[0]-lower[0])/max(upper[0],lower[0])*100
        leg_difference=abs(thigh[0]-calf[0])/max(thigh[0],calf[0])*100
        torso_ratio=abs(hip_y-shoulder_y)/max(abs(ankle_y-hip_y),1e-6)*100
        return {"upper_lower_arm_length_difference_percent":arm_difference,"thigh_calf_length_difference_percent":leg_difference,"torso_to_lower_limb_ratio_percent":torso_ratio}
    finally:
        if prompt_id and not prompt_finished:
            _cancel_comfy_prompt(prompt_id)
        if job_id:
            try:
                _assert_image_job_runnable(job_id)
                _update_image_job(job_id, validation_prompt_id="", heartbeat_at=_iso_now())
            except Exception:
                pass
        input_path.unlink(missing_ok=True)
        for match in COMFY_OUTPUT.glob(f"{prefix}_*.json"): match.unlink(missing_ok=True)


def _head_body_ratio(
    candidate: Path, *, job_id: str = "", deadline: float | None = None,
) -> float | None:
    script = r'''import json,sys,cv2
from insightface.app import FaceAnalysis
from ultralytics import YOLO
image=cv2.imread(sys.argv[1]); app=FaceAnalysis(name="buffalo_l",root=sys.argv[2],providers=["CPUExecutionProvider"]); app.prepare(ctx_id=-1,det_size=(1024,1024))
enlarged=cv2.resize(image,None,fx=2.0,fy=2.0,interpolation=cv2.INTER_CUBIC); faces=app.get(enlarged); result=YOLO("/Users/aoo/AI/ComfyUI-Shared/models/yolo11n.pt")(sys.argv[1],verbose=False)[0]
people=[box for cls,conf,box in zip(result.boxes.cls,result.boxes.conf,result.boxes.xyxy) if int(cls)==0 and float(conf)>=0.25]
if not faces or len(people)!=1: print("null")
else:
 face=max(faces,key=lambda item:float((item.bbox[2]-item.bbox[0])*(item.bbox[3]-item.bbox[1]))); person=people[0]
 face_h=float(face.bbox[3]-face.bbox[1])*0.5*1.45; body_h=float(person[3]-person[1]); print(json.dumps(body_h/max(face_h,1.0)))
'''
    stdout = _run_image_validation_subprocess(
        [str(COMFY_PYTHON), "-c", script, str(candidate), "/Users/aoo/AI/Models/Vision/InsightFace"],
        job_id=job_id, deadline=deadline, maximum=180,
    )
    payload = json.loads(stdout.strip().splitlines()[-1])
    return float(payload) if isinstance(payload, (int,float)) else None


def _png_dimensions(path: Path) -> tuple[int, int] | None:
    header = path.read_bytes()[:24]
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return struct.unpack(">II", header[16:24])


def _required_image_text(body: dict, prompt: str) -> str:
    """Return only explicitly requested in-world text; dialogue and asset names are never inferred."""
    explicit = re.sub(r"\s+", "", str(body.get("required_text") or "").strip())
    if explicit:
        return explicit[:24]
    patterns = (
        r"(?:写有|写着|题有|题字为|字样为|文字为|显示为)[“\"「『【]?([\u3400-\u9fffA-Za-z0-9·]{1,24})",
        r"(?:刻有|雕刻文字为)[“\"「『【]([\u3400-\u9fffA-Za-z0-9·]{1,24})[”\"」』】]",
        r"(?:招牌|牌匾|门匾|石碑|卷轴)(?:上)?(?:写有|写着|题有|题着|为|：|:)[“\"「『【]?([\u3400-\u9fffA-Za-z0-9·]{1,24})",
    )
    for pattern in patterns:
        match = re.search(pattern, prompt)
        if match:
            return match.group(1).rstrip("”\"」』】。，；、")[:24]
    return ""


def _blank_requested_text(prompt: str, required_text: str) -> str:
    if not required_text:
        return prompt
    blanked = prompt.replace(required_text, "")
    return (
        f"{blanked}\n文字后处理硬约束：画面内需要承载文字的位置必须保留为干净、完整、无遮挡的纯色空白牌面；"
        "当前生图阶段禁止生成任何汉字、字母、数字、符号、书法、标志或水印。"
    )


def _sanitize_no_text_asset_prompt(prompt: str) -> str:
    """Remove positive glyph requests from assets whose contract forbids text."""
    cue = re.compile(r"(?:笔迹|字迹|文字|字样|书法|铭文|刻字|题字|标签|标牌|招牌|水印|logo|letters?|text|signage)", re.IGNORECASE)
    before_negative = re.compile(r"(?:无|没有|禁止|不得|不要|避免|去除|不含|干净|空白|no|without)(?:(?:任何|出现|生成|包含|含有|可见的|visible)\s*){0,3}$", re.IGNORECASE)
    after_negative = re.compile(r"^\s*(?:必须)?(?:不得|禁止|不能|不可|不应|不要|应当去除|必须去除|必须没有|must\s+not|is\s+forbidden)", re.IGNORECASE)
    def has_positive_cue(value: str) -> bool:
        for match in cue.finditer(value):
            if before_negative.search(value[max(0, match.start() - 12):match.start()]):
                continue
            if after_negative.search(value[match.end():match.end() + 16]):
                continue
            return True
        return False
    clauses = re.split(r"([，。；;\n])", str(prompt or ""))
    sanitized: list[str] = []
    for clause in clauses:
        if clause in {"，", "。", "；", ";", "\n"}:
            sanitized.append(clause)
            continue
        if not has_positive_cue(clause):
            sanitized.append(clause)
            continue
        # A model may combine a forbidden glyph detail with valid material
        # detail using “or/and”. Keep only the independently valid fragments.
        fragments = re.split(r"(?:或|以及|并且|与|和|\bor\b|\band\b)", clause, flags=re.IGNORECASE)
        sanitized.append("，".join(fragment.strip() for fragment in fragments if fragment.strip() and not has_positive_cue(fragment)))
    value = re.sub(r"[，。；;]{2,}", "，", "".join(sanitized)).strip("，。；; \n")
    return f"{value}。道具表面必须完全无字、无字形、无标签、无标志、无水印。" if value else "单个道具本体，表面完全无字、无字形、无标签、无标志、无水印。"


def _apply_required_text_overlay(path: Path, text: str, body: dict) -> dict:
    """Render exact text deterministically; the diffusion model never draws glyphs."""
    if not text:
        return {"required_text":"", "text_overlay_applied":False, "text_audit":"not_applicable"}
    direction = str(body.get("text_direction") or "vertical").lower()
    anchor = str(body.get("text_anchor") or "right").lower()
    color = str(body.get("text_color") or "#f5d742")
    font = Path("/System/Library/Fonts/Supplemental/Songti.ttc")
    script = r'''from PIL import Image,ImageDraw,ImageFont
import json,sys,hashlib
source,text,font_path,direction,anchor,color=sys.argv[1:7]
image=Image.open(source).convert("RGBA"); w,h=image.size
layer=Image.new("RGBA",image.size,(0,0,0,0)); draw=ImageDraw.Draw(layer)
vertical=direction!="horizontal"
font_size=max(28,int((h*0.52/max(len(text),1)) if vertical else (w*0.68/max(len(text),1))))
font_size=min(font_size,int(h*0.105),int(w*0.16))
font=ImageFont.truetype(font_path,font_size,index=1)
stroke=max(1,font_size//24); spacing=max(3,font_size//9)
if vertical:
    boxes=[draw.textbbox((0,0),ch,font=font,stroke_width=stroke) for ch in text]
    block_w=max(box[2]-box[0] for box in boxes); block_h=sum(box[3]-box[1] for box in boxes)+spacing*(len(text)-1)
    x=int(w*0.76-block_w/2) if anchor=="right" else int(w*0.24-block_w/2) if anchor=="left" else int((w-block_w)/2)
    y=max(int(h*0.12),int((h-block_h)/2))
    pad_x=max(16,font_size//3); pad_y=max(20,font_size//3); radius=max(8,font_size//8)
    draw.rounded_rectangle((x-pad_x,y-pad_y,x+block_w+pad_x,y+block_h+pad_y),radius=radius,fill=(5,8,18,232),outline=(126,98,24,255),width=max(2,stroke))
    for ch,box in zip(text,boxes):
        ch_h=box[3]-box[1]; draw.text((x,y),ch,font=font,fill=color,stroke_width=stroke,stroke_fill="#201b12")
        y+=ch_h+spacing
else:
    box=draw.textbbox((0,0),text,font=font,stroke_width=stroke); tw,th=box[2]-box[0],box[3]-box[1]
    x=int(w*0.06) if anchor=="left" else int(w*0.94-tw) if anchor=="right" else int((w-tw)/2)
    y=int(h*0.18) if anchor=="top" else int(h*0.80-th) if anchor=="bottom" else int((h-th)/2)
    pad_x=max(18,font_size//3); pad_y=max(12,font_size//4); radius=max(8,font_size//8)
    draw.rounded_rectangle((x-pad_x,y-pad_y,x+tw+pad_x,y+th+pad_y),radius=radius,fill=(5,8,18,232),outline=(126,98,24,255),width=max(2,stroke))
    draw.text((x,y),text,font=font,fill=color,stroke_width=stroke,stroke_fill="#201b12")
Image.alpha_composite(image,layer).convert("RGB").save(source,"PNG",compress_level=3)
print(json.dumps({"sha256":hashlib.sha256(text.encode()).hexdigest(),"direction":"vertical" if vertical else "horizontal","anchor":anchor},ensure_ascii=False))
'''
    result = subprocess.run(
        [str(COMFY_PYTHON), "-c", script, str(path), text, str(font), direction, anchor, color],
        check=True, capture_output=True, text=True, timeout=120,
    )
    evidence = json.loads(result.stdout.strip().splitlines()[-1])
    return {"required_text":text, "text_overlay_applied":True, "text_audit":"exact_source_render", "text_render":evidence}


def _normalize_character_baseline_crop(path: Path) -> None:
    """Normalize a portrait to 928x1664, a 45% face, and a complete hairstyle."""
    script = r'''import cv2,sys,numpy as np
from insightface.app import FaceAnalysis
source,models=sys.argv[1],sys.argv[2]
image=cv2.imread(source)
app=FaceAnalysis(name="buffalo_l",root=models,providers=["CPUExecutionProvider"])
app.prepare(ctx_id=-1,det_size=(640,640))
faces=app.get(image)
if len(faces)!=1: raise RuntimeError(f"face_count={len(faces)}")
x1,y1,x2,y2=map(float,faces[0].bbox)
face_h=max(1.0,y2-y1); face_w=max(1.0,x2-x1); scale=(1664.0*0.45)/face_h
# InsightFace excludes hair. Find the first dark-hair row above the face and
# enforce 5% top and 2% left/right safety margins for the complete hairstyle.
gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY)
roi_left=max(0,int(x1-face_w*0.55)); roi_right=min(image.shape[1],int(x2+face_w*0.55))
search_bottom=max(1,min(image.shape[0],int(y1+face_h*0.20)))
corner=np.concatenate((gray[:max(8,image.shape[0]//12),:max(8,image.shape[1]//10)].ravel(),gray[:max(8,image.shape[0]//12),-max(8,image.shape[1]//10):].ravel()))
background=float(np.median(corner)); dark=gray[:search_bottom,roi_left:roi_right] < background-28
rows=np.where(dark.sum(axis=1) >= max(8,int(dark.shape[1]*0.08)))[0]
hair_top=float(rows[0]) if len(rows) else max(0.0,y1-face_h*0.45)
cols=np.where(dark.sum(axis=0) >= max(8,int(dark.shape[0]*0.04)))[0]
hair_left=float(roi_left+cols[0]) if len(cols) else max(0.0,x1-face_w*0.45)
hair_right=float(roi_left+cols[-1]+1) if len(cols) else min(float(image.shape[1]),x2+face_w*0.45)
hair_width=max(1.0,hair_right-hair_left)
scale=min(scale,(928.0*0.96)/hair_width)
scaled=cv2.resize(image,None,fx=scale,fy=scale,interpolation=cv2.INTER_LANCZOS4)
hair_cx=(hair_left+hair_right)*0.5*scale
left=int(round(hair_cx-928/2)); top=int(round(hair_top*scale-1664*0.05))
right=left+928; bottom=top+1664
pad_l=max(0,-left); pad_t=max(0,-top); pad_r=max(0,right-scaled.shape[1]); pad_b=max(0,bottom-scaled.shape[0])
if pad_l or pad_t or pad_r or pad_b:
    scaled=cv2.copyMakeBorder(scaled,pad_t,pad_b,pad_l,pad_r,cv2.BORDER_CONSTANT,value=(128,128,128))
    left+=pad_l; top+=pad_t
crop=scaled[top:top+1664,left:left+928]
if crop.shape[:2]!=(1664,928): raise RuntimeError(f"crop_shape={crop.shape}")
cv2.imwrite(source,crop,[cv2.IMWRITE_PNG_COMPRESSION,3])
'''
    subprocess.run(
        [str(COMFY_PYTHON), "-c", script, str(path), "/Users/aoo/AI/Models/Vision/InsightFace"],
        check=True, capture_output=True, text=True, timeout=180,
    )


def _normalize_character_variant_margins(path: Path) -> dict:
    """Normalize a detected person and return measured pixel-space frame evidence."""
    script = r'''import cv2,json,sys,numpy as np
from ultralytics import YOLO
source=sys.argv[1]
image=cv2.imread(source)
if image is None: raise RuntimeError("image_unreadable")
h,w=image.shape[:2]
model=YOLO("/Users/aoo/AI/ComfyUI-Shared/models/yolo11n.pt")
result=model(source,verbose=False)[0]
people=[]
for cls,conf,box in zip(result.boxes.cls,result.boxes.conf,result.boxes.xyxy):
    if int(cls)==0 and float(conf)>=0.25:
        x1,y1,x2,y2=[float(v) for v in box]
        people.append((float(conf),x1,y1,x2-x1,y2-y1))
# Long robes in strict profile are frequently classified as clothing objects
# instead of COCO person.  Asset portraits have a required seamless neutral
# background, so derive a second deterministic foreground seed from the image
# border instead of treating YOLO as the sole source of truth.
mask=np.zeros((h,w),np.uint8)
grabcut_mode=cv2.GC_INIT_WITH_RECT
if len(people)==1:
    _,x,y,bw,bh=people[0]
else:
    # Preliminary full-frame GrabCut is robust to the subtle studio gradient
    # and floor shadow that defeat a single global background-color threshold.
    preliminary=np.zeros((h,w),np.uint8)
    preliminary_bgd=np.zeros((1,65),np.float64); preliminary_fgd=np.zeros((1,65),np.float64)
    preliminary_rect=(max(1,int(w*0.03)),max(1,int(h*0.015)),max(2,int(w*0.94)),max(2,int(h*0.965)))
    cv2.grabCut(image,preliminary,preliminary_rect,preliminary_bgd,preliminary_fgd,5,cv2.GC_INIT_WITH_RECT)
    foreground=np.where((preliminary==cv2.GC_FGD)|(preliminary==cv2.GC_PR_FGD),255,0).astype(np.uint8)
    foreground=cv2.morphologyEx(foreground,cv2.MORPH_CLOSE,np.ones((5,5),np.uint8))
    count,labels,stats,_=cv2.connectedComponentsWithStats(foreground,8)
    candidates=[i for i in range(1,count) if stats[i,cv2.CC_STAT_AREA]>=int(h*w*0.025) and stats[i,cv2.CC_STAT_HEIGHT]>=int(h*0.35)]
    if len(candidates)!=1:
        raise RuntimeError(f"person_count={len(people)};foreground_count={len(candidates)}")
    owner=candidates[0]
    x,y,bw,bh=[float(v) for v in stats[owner,:4]]
if y<=1 or y+bh>=h-1: raise RuntimeError(f"person_touches_vertical_edge:{y},{y+bh},{h}")
if bh<h*0.35: raise RuntimeError(f"person_height_invalid:{x},{y},{bw},{bh}")
# Refine the detector rectangle to the visible silhouette. Detection boxes can
# start below dark hair or end above shoe soles, so they cannot prove margins.
gx1=max(1,int(np.floor(x-bw*0.025))); gy1=max(1,int(np.floor(y-bh*0.015)))
gx2=min(w-1,int(np.ceil(x+bw*1.025))); gy2=min(h-1,int(np.ceil(y+bh*1.015)))
rect=(gx1,gy1,max(2,gx2-gx1),max(2,gy2-gy1))
bgd=np.zeros((1,65),np.float64); fgd=np.zeros((1,65),np.float64)
try:
    cv2.grabCut(image,mask,rect,bgd,fgd,5,grabcut_mode)
    foreground=np.where((mask==cv2.GC_FGD)|(mask==cv2.GC_PR_FGD),255,0).astype(np.uint8)
    foreground=cv2.morphologyEx(foreground,cv2.MORPH_CLOSE,np.ones((5,5),np.uint8))
    count,labels,stats,_=cv2.connectedComponentsWithStats(foreground,8)
    cx=min(w-1,max(0,int(round(x+bw/2)))); cy=min(h-1,max(0,int(round(y+bh/2))))
    owner=int(labels[cy,cx])
    if owner<=0:
        candidates=[i for i in range(1,count) if stats[i,cv2.CC_STAT_AREA]>=max(64,int(bw*bh*0.08))]
        owner=max(candidates,key=lambda i:stats[i,cv2.CC_STAT_AREA]) if candidates else 0
    if owner<=0: raise RuntimeError("foreground_component_missing")
    sx,sy,sw,sh=[float(v) for v in stats[owner,:4]]
    if sh<bh*0.72 or sw<bw*0.35: raise RuntimeError(f"foreground_component_invalid:{sx},{sy},{sw},{sh}")
except Exception as error:
    raise RuntimeError(f"foreground_segmentation_failed:{type(error).__name__}:{error}") from error
# Reserve tolerance beyond the public 8%/3% contract. The final deterministic
# evidence is calculated from this same refined silhouette, not asserted by flag.
target_h=1664*0.86
target_w=928*0.88
scale=min(target_h/sh,target_w/sw)
resized=cv2.resize(image,None,fx=scale,fy=scale,interpolation=cv2.INTER_LANCZOS4)
rx,ry,rw,rh=[value*scale for value in (sx,sy,sw,sh)]
left=int(round(rx+rw/2-928/2)); top=int(round(ry-1664*0.09))
right=left+928; bottom=top+1664
pad_l=max(0,-left); pad_t=max(0,-top); pad_r=max(0,right-resized.shape[1]); pad_b=max(0,bottom-resized.shape[0])
if pad_l or pad_t or pad_r or pad_b:
    resized=cv2.copyMakeBorder(resized,pad_t,pad_b,pad_l,pad_r,cv2.BORDER_REPLICATE)
    rx+=pad_l; ry+=pad_t
    left+=pad_l; top+=pad_t
crop=resized[top:top+1664,left:left+928]
if crop.shape[:2]!=(1664,928): raise RuntimeError(f"crop_shape={crop.shape}")
cv2.imwrite(source,crop,[cv2.IMWRITE_PNG_COMPRESSION,3])
out_x1=rx-left; out_y1=ry-top; out_x2=rx+rw-left; out_y2=ry+rh-top
evidence={
    "source":"grabcut_person_silhouette",
    "subject_bounds":[round(out_x1,3),round(out_y1,3),round(out_x2,3),round(out_y2,3)],
    "top_margin_ratio":round(max(0.0,out_y1/1664.0),6),
    "bottom_margin_ratio":round(max(0.0,(1664.0-out_y2)/1664.0),6),
    "left_margin_ratio":round(max(0.0,out_x1/928.0),6),
    "right_margin_ratio":round(max(0.0,(928.0-out_x2)/928.0),6),
    "output_width":928,"output_height":1664,
}
evidence["top_margin_at_least_8_percent"]=evidence["top_margin_ratio"]>=0.08
evidence["bottom_margin_at_least_3_percent"]=evidence["bottom_margin_ratio"]>=0.03
if not evidence["top_margin_at_least_8_percent"] or not evidence["bottom_margin_at_least_3_percent"]:
    raise RuntimeError("normalized_margin_contract_failed:"+json.dumps(evidence,separators=(",",":")))
print(json.dumps(evidence,separators=(",",":")))
'''
    result = subprocess.run(
        [str(COMFY_PYTHON), "-c", script, str(path)],
        check=True, capture_output=True, text=True, timeout=180,
    )
    evidence = json.loads(result.stdout.strip().splitlines()[-1])
    if (
        evidence.get("output_width") != 928
        or evidence.get("output_height") != 1664
        or evidence.get("top_margin_at_least_8_percent") is not True
        or evidence.get("bottom_margin_at_least_3_percent") is not True
    ):
        raise RuntimeError(f"人物安全区确定性归一失败：{json.dumps(evidence, ensure_ascii=False)}")
    return evidence


def _flux_identity_prompt(description: str) -> str:
    """Keep identity attributes at the front in FLUX's strongest prompt language."""
    translated = description
    replacements = {
        "女性":"young Chinese woman", "男性":"young Chinese man", "圆润脸型":"round face",
        "方脸":"square face", "高鼻梁":"high nose bridge", "杏眼":"almond-shaped eyes",
        "细长眼":"narrow eyes", "长睫毛":"long eyelashes", "浓眉":"thick eyebrows",
        "齐肩黑发":"shoulder-length black hair", "短发":"short black hair", "发丝自然垂落":"loose natural hair",
        "身形纤细":"slender build", "身形健硕":"athletic muscular build", "身穿淡青色长裙":"wearing a pale cyan traditional Chinese long dress",
        "身穿黑色劲装":"wearing a fitted black traditional Chinese martial outfit", "腰间系玉佩":"with a jade pendant at the waist",
        "腰间佩剑":"with a sword at the waist", "国风浅涂风格":"realistic Chinese period-drama styling",
        "低饱和古风":"muted historical Chinese palette", "柔和天光":"soft daylight",
    }
    for source, target in replacements.items():
        translated = translated.replace(source, target)
    translated = re.sub(r"(\d{1,2})岁", r"\1 years old", translated)
    return translated


def _verified_character_frame_margins(image: dict) -> tuple[bool, bool, dict]:
    """Require numeric normalizer evidence; a legacy boolean flag is never sufficient."""
    metrics = image.get("deterministic_frame_metrics")
    if (
        not isinstance(metrics, dict)
        or image.get("normalized_variant_margins") is not True
        or metrics.get("source") != "grabcut_person_silhouette"
    ):
        return False, False, {}
    try:
        top_ratio = float(metrics.get("top_margin_ratio"))
        bottom_ratio = float(metrics.get("bottom_margin_ratio"))
    except (TypeError, ValueError):
        return False, False, metrics
    top_valid = metrics.get("top_margin_at_least_8_percent") is True and top_ratio >= 0.08
    bottom_valid = metrics.get("bottom_margin_at_least_3_percent") is True and bottom_ratio >= 0.03
    return top_valid, bottom_valid, metrics


def _prepare_character_full_frame_candidate(image: dict) -> tuple[bool, dict]:
    """Normalize one full-frame candidate or remove it before a bounded retry."""
    source = _local_media_path(image.get("url"))
    try:
        metrics = _normalize_character_variant_margins(source)
    except Exception as error:
        source.unlink(missing_ok=True)
        return False, {
            "normalization_failed": True,
            "error": str(error),
            "source_removed": not source.exists(),
        }
    image["deterministic_frame_metrics"] = metrics
    image["normalized_variant_margins"] = True
    return True, metrics


def _run_character_full_frame_candidate_loop(
    initial_image: dict,
    *,
    generate_retry,
    validate_candidate,
    max_attempts: int,
    on_attempt=None,
) -> tuple[dict, str, int]:
    """Own candidate cleanup and bounded regeneration for every full-frame caller."""
    image = initial_image
    evidence = ""
    for attempt in range(max_attempts):
        if on_attempt is not None:
            on_attempt(attempt + 1)
        normalized, frame_evidence = _prepare_character_full_frame_candidate(image)
        if normalized:
            valid, evidence = validate_candidate(image)
            if valid:
                return image, evidence, attempt + 1
            _local_media_path(image.get("url")).unlink(missing_ok=True)
        else:
            evidence = json.dumps(frame_evidence, ensure_ascii=False)
        if attempt == max_attempts - 1:
            raise RuntimeError(f"character_full_frame_candidates_exhausted:{evidence}")
        image = generate_retry(attempt + 2, evidence)
    raise RuntimeError("character_full_frame_candidates_exhausted:unreachable")


def _validate_character_baseline(image: dict, identity_prompt: str = "") -> tuple[bool, str]:
    """Validate the non-negotiable first character-reference composition."""
    source = _local_media_path(image.get("url"))
    encoded = base64.b64encode(source.read_bytes()).decode("ascii")
    request = Request(
        "http://127.0.0.1:11434/api/generate",
        data=json.dumps({
            "model": "llava:latest",
            "prompt": (
                "Look at the image and answer these visual questions as JSON with true or false only: "
                '{"exactly_one_person":...,"plain_gray_background":...,"visible_hands":...,'
                '"held_prop":...,"body_below_chest_visible":...,"front_facing":...,'
                '"direct_gaze":...,"neutral_expression":...,"is_collage":...,'
                '"has_text_or_annotations":...,"face_height_40_to_50_percent":...,"gender_and_age_match":...,"face_hair_match":...,"clothing_match":...}. '
                "For the final three fields compare the visible person literally with this required identity description: "
                f"{identity_prompt}. Clothing_match is false when the specified garment type or color is absent; "
                "gender_and_age_match is false when the apparent age differs materially. Do not explain."
            ),
            "images": [encoded], "stream": False, "keep_alive": 0, "format": "json",
            "options": {"num_ctx": 1536, "num_predict": 320, "temperature": 0, "seed": 11},
        }).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with _claim_production_resource("audit", f"character-baseline-audit-{uuid4()}", timeout=900):
        _require_memory(12 * GIB)
        with urlopen(request, timeout=600) as response:
            payload = json.loads(response.read())
    evidence = str(payload.get("response", "")).strip()
    match = re.search(r"\{[\s\S]*\}", evidence)
    if not match:
        return False, evidence[:500] or "视觉模型未返回结构化验收结果"
    try:
        verdict = json.loads(match.group(0))
    except json.JSONDecodeError:
        return False, evidence[:500]
    # Identity baselines must be usable for downstream face locking. Background tone and
    # crop tightness are quality hints, not reasons to discard an otherwise valid identity.
    pose = _face_pose_angles(source)
    pose_valid = pose is not None and abs(pose[1]) <= 3.0 and abs(pose[2]) <= 3.0
    verdict["face_pose"] = list(pose) if pose else None
    verdict["strict_zero_degree_face"] = pose_valid
    dimensions = _png_dimensions(source)
    verdict["pixel_dimensions"] = list(dimensions) if dimensions else None
    verdict["required_928x1664"] = dimensions == (928, 1664)
    # Baseline identity, hair and clothing are deliberately confirmed by the user.
    # The local VLM is retained as evidence only because repeated real-image tests
    # showed unstable false negatives. Automatic admission is limited to objective,
    # deterministic facts after the crop normalizer has found exactly one face.
    valid = (
        verdict.get("required_928x1664") is True
        and pose_valid
        and verdict.get("front_facing") is True
        and verdict.get("direct_gaze") is True
    )
    return valid, json.dumps(verdict, ensure_ascii=False)


CHARACTER_FULL_BODY_ANATOMY_CHECKS = (
    "hands_anatomically_valid",
    "feet_anatomically_valid",
    "no_fused_missing_or_extra_limbs_or_digits",
)


def _character_variant_required_checks(target_pose: str, strict_clothing_reference: bool) -> tuple[str, ...]:
    required = ("exactly_one_person", "correct_orientation", "body_shape_consistent", "natural_body_proportion", "top_margin_at_least_8_percent", "bottom_margin_at_least_3_percent", "head_to_body_ratio_7_to_7_8", "plain_background", "required_928x1664", "deterministic_full_frame")
    if target_pose not in {"front_full", "front_half", "left_45_full", "right_45_full"}:
        required += ("full_head_visible", "feet_visible", "thigh_calf_difference_within_8_percent", "upper_lower_arm_difference_within_10_percent", "torso_at_least_55_percent_of_lower_limb")
    if target_pose == "side_90_full":
        required += ("strict_side_face_88_to_92", "torso_rotation_within_3_degrees")
    if strict_clothing_reference:
        required += ("exact_clothing_consistent", "hair_consistent", "clothing_similarity_at_least_0_82")
    if target_pose == "front_full":
        required += ("deterministic_full_frame", "identity_consistent", "face_similarity_calibrated_front")
    elif target_pose == "front_half":
        return ("exactly_one_person", "correct_orientation", "full_head_visible", "identity_consistent", "hair_consistent", "plain_background", "required_928x1664", "face_similarity_calibrated_front", "waist_crop", "hands_out_of_frame", "subject_height_about_75_percent", "shoulders_clear_of_edges", "balanced_side_margins")
    elif target_pose == "left_45_full":
        return ("exactly_one_person", "correct_orientation", "top_margin_at_least_8_percent", "bottom_margin_at_least_3_percent", "plain_background", "required_928x1664", "deterministic_full_frame", "left_45_face_angle_30_to_60", *CHARACTER_FULL_BODY_ANATOMY_CHECKS)
    elif target_pose == "right_45_full":
        return ("exactly_one_person", "correct_orientation", "top_margin_at_least_8_percent", "bottom_margin_at_least_3_percent", "plain_background", "required_928x1664", "deterministic_full_frame", "right_45_face_angle_minus_60_to_minus_30", *CHARACTER_FULL_BODY_ANATOMY_CHECKS)
    if target_pose in {"side_90_full", "back_full"}:
        required += CHARACTER_FULL_BODY_ANATOMY_CHECKS
    return required


def _character_variant_verdict_passes(verdict: dict, target_pose: str, strict_clothing_reference: bool) -> bool:
    return all(verdict.get(key) is True for key in _character_variant_required_checks(target_pose, strict_clothing_reference))


def _validate_character_variant(
    reference_url: str,
    image: dict,
    target_pose: str,
    clothing_reference_url: str = "",
    *,
    job_id: str = "",
    deadline: float | None = None,
) -> tuple[bool, str]:
    """Reject wrong direction, cropped feet, identity drift and distorted body proportions."""
    reference = _reference_path(reference_url)
    clothing_reference = _reference_path(clothing_reference_url) if clothing_reference_url else None
    strict_clothing_reference = clothing_reference if target_pose in {"left_45_full", "right_45_full", "side_90_full", "back_full"} else None
    candidate = _local_media_path(image.get("url"))
    pose_label = {"left_45_full":"左45度全身", "right_45_full":"右45度全身", "front_full":"0度正面全身", "side_90_full":"90度纯侧面全身", "back_full":"180度纯背面全身", "front_half":"0度正面半身"}.get(target_pose, target_pose)
    request = Request(
        "http://127.0.0.1:11434/api/generate",
        data=json.dumps({
            "model":"llava:latest",
            "prompt":(
                f"The first image is the accepted zero-degree front full-body identity baseline. The second image must be a {pose_label} asset. "
                "Inspect the second image edges literally and compare face and hair with the first image. Return JSON booleans only: "
                '{"exactly_one_person":...,"full_head_visible":...,"feet_visible":...,'
                '"correct_orientation":...,"identity_consistent":...,"hair_consistent":...,"exact_clothing_consistent":...,"body_shape_consistent":...,'
                '"natural_body_proportion":...,"top_margin_at_least_8_percent":...,"bottom_margin_at_least_3_percent":...,"head_to_body_ratio_7_to_7_8":...,"plain_background":...,'
                '"hands_anatomically_valid":...,"feet_anatomically_valid":...,"no_fused_missing_or_extra_limbs_or_digits":...,'
                '"head_to_body_ratio":0.0,"thigh_calf_length_difference_percent":0.0,"upper_lower_arm_length_difference_percent":0.0,"torso_to_lower_limb_ratio_percent":0.0,'
                '"waist_crop":...,"hands_out_of_frame":...,"subject_height_about_75_percent":...,"shoulders_clear_of_edges":...,"balanced_side_margins":...}. '
                "Set full_head_visible=true when the complete top of the head is inside the image frame. "
                "Set feet_visible=true when both feet and shoes are visible and not cut by an image edge. "
                "Set top_margin_at_least_8_percent=true only when the pure background above the highest hair point is 8 percent or more of image height; 8 percent is a minimum, not a fixed target. "
                "Set bottom_margin_at_least_3_percent=true only when the pure background below the lowest shoe sole is 3 percent or more of image height; 3 percent is a minimum, not a fixed target. "
                "Measure the numeric body ratios from visible anatomical joints. Set head_to_body_ratio_7_to_7_8=true only from 7.0 through 7.8; thigh/calf difference must be at most 8 percent; upper/lower arm difference at most 10 percent; torso height must be at least 55 percent of the full lower-limb height. "
                "Inspect every visible arm, wrist, hand, finger, leg, ankle, foot and toe at high attention. Set hands_anatomically_valid=false for fused fingers, missing or extra fingers, melted knuckles, broken wrists, duplicated hands or hand-shaped blobs. Set feet_anatomically_valid=false for fused feet, missing or extra toes, broken ankles, duplicated feet or foot-shaped blobs. Set no_fused_missing_or_extra_limbs_or_digits=false for any fused, missing, extra, duplicated or disconnected limb or digit. Occlusion by the body or garment is allowed only when the anatomy is naturally hidden rather than malformed. "
                "For a side view also return numeric fields side_face_angle_degrees and torso_rotation_degrees. "
                "Measure side_face_angle_degrees from frontal zero toward a pure profile at 90 degrees. Measure torso_rotation_degrees as deviation from a pure side torso; pure stacked shoulders and hips is zero. "
                "For a side view only one facial profile may be visible; for a back view no face or front chest may be visible. "
                "For a front_half view require an eye-level zero-degree close-up half-body portrait: crop exactly at the waist, keep both hands entirely outside the frame, keep the complete head with only a tiny top margin, make the head-to-waist subject occupy approximately 75 percent of image height, and keep both shoulders clear of the side edges with balanced margins. "
                "For a side view set correct_orientation=false if the back, front chest, both shoulders, both separated arms or both separated legs are visible; the entire body and face must form one strict 90-degree profile. "
                "Judge identity by face geometry, hairline and overall appearance; for a back view use rear hair, clothing and body shape. Do not explain."
            ),
            "images":[base64.b64encode(path.read_bytes()).decode("ascii") for path in [reference, candidate]],
            "stream":False, "keep_alive":0, "format":"json",
            "options":{"num_ctx":3072,"num_predict":640,"temperature":0,"seed":17},
        }).encode("utf-8"),
        headers={"Content-Type":"application/json"}, method="POST",
    )
    if job_id:
        _assert_image_job_runnable(job_id)
    resource_identity = _image_job_identity(job_id)
    claim_timeout = max(0.1, deadline - time.monotonic()) if deadline is not None else IMAGE_VALIDATION_TIMEOUT_SECONDS
    with _claim_production_resource(
        "audit", job_id or f"character-angle-audit-{uuid4()}", timeout=claim_timeout,
        identity=resource_identity or None,
    ):
        if job_id:
            _assert_image_job_runnable(job_id)
        _require_memory(12 * GIB)
        response_timeout = max(0.1, deadline - time.monotonic()) if deadline is not None else IMAGE_VALIDATION_TIMEOUT_SECONDS
        with urlopen(request, timeout=response_timeout) as response: payload = json.loads(response.read())
    if job_id:
        _assert_image_job_runnable(job_id)
    evidence = str(payload.get("response", "")).strip()
    match = re.search(r"\{[\s\S]*\}", evidence)
    if not match: return False, evidence[:500] or "固定角度视觉模型未返回结构化结果"
    try: verdict = json.loads(match.group(0))
    except json.JSONDecodeError: return False, evidence[:500]
    if strict_clothing_reference:
        clothing_request = Request(
            "http://127.0.0.1:11434/api/generate",
            data=json.dumps({
                "model":"llava:latest",
                "prompt":(
                    "The first image is the accepted character reference and the second is the generated full-body candidate. "
                    "Return JSON only: {\"exact_clothing_consistent\":...,\"body_shape_consistent\":...,\"hair_consistent\":...,\"identity_consistent\":...,\"clothing_similarity_score\":0.0}. "
                    "For clothing, compare every visible cue in the accepted reference literally: main color, collar shape, fabric style, trim, fastener and simplicity. "
                    "False if the candidate adds brocade, large patterns, armor, cape, robe layers, contrasting waist panels or ceremonial decoration not visible or requested. "
                    "For hair, compare color, bangs, parting, tied/loose state, braid or ponytail and visible length. False for any changed hairstyle. "
                    "For identity, compare apparent age, face shape and facial features. Do not excuse differences caused by the full-body crop. Do not explain."
                ),
                "images":[base64.b64encode(path.read_bytes()).decode("ascii") for path in [strict_clothing_reference, candidate]],
                "stream":False,"keep_alive":0,"format":"json",
                "options":{"num_ctx":2048,"num_predict":160,"temperature":0,"seed":19},
            }).encode("utf-8"),
            headers={"Content-Type":"application/json"}, method="POST",
        )
        if job_id:
            _assert_image_job_runnable(job_id)
        claim_timeout = max(0.1, deadline - time.monotonic()) if deadline is not None else IMAGE_VALIDATION_TIMEOUT_SECONDS
        with _claim_production_resource(
            "audit", job_id or f"character-clothing-audit-{uuid4()}", timeout=claim_timeout,
            identity=resource_identity or None,
        ):
            if job_id:
                _assert_image_job_runnable(job_id)
            _require_memory(12 * GIB)
            response_timeout = max(0.1, deadline - time.monotonic()) if deadline is not None else IMAGE_VALIDATION_TIMEOUT_SECONDS
            with urlopen(clothing_request, timeout=response_timeout) as response:
                clothing_payload = json.loads(response.read())
        if job_id:
            _assert_image_job_runnable(job_id)
        try:
            clothing_verdict = json.loads(str(clothing_payload.get("response", "")).strip())
        except json.JSONDecodeError:
            clothing_verdict = {}
        verdict["exact_clothing_consistent"] = clothing_verdict.get("exact_clothing_consistent") is True
        verdict["body_shape_consistent"] = clothing_verdict.get("body_shape_consistent") is True
        verdict["hair_consistent"] = verdict.get("hair_consistent") is True and clothing_verdict.get("hair_consistent") is True
        verdict["identity_consistent"] = verdict.get("identity_consistent") is True and clothing_verdict.get("identity_consistent") is True
        try:
            clothing_similarity = float(clothing_verdict.get("clothing_similarity_score"))
        except (TypeError, ValueError):
            clothing_similarity = 0.0
        verdict["clothing_similarity_score"] = clothing_similarity
        verdict["clothing_similarity_at_least_0_82"] = clothing_similarity >= 0.82
    if target_pose != "front_half" and (verdict.get("full_head_visible") is not True or verdict.get("feet_visible") is not True):
        frame_request = Request(
            "http://127.0.0.1:11434/api/generate",
            data=json.dumps({
                "model":"llava:latest",
                "prompt":(
                    "Inspect the single full-body person. Return JSON only: "
                    '{"top_of_head_inside_frame":true_or_false,"both_feet_and_shoes_inside_frame":true_or_false,'
                    '"full_body_from_head_to_feet_visible":true_or_false,"plain_studio_background":true_or_false}. '
                    "A small margin is not required; visible means no body part is cut by an image edge."
                ),
                "images":[base64.b64encode(candidate.read_bytes()).decode("ascii")],
                "stream":False, "keep_alive":0, "format":"json",
                "options":{"num_predict":128,"temperature":0,"seed":23},
            }).encode("utf-8"),
            headers={"Content-Type":"application/json"}, method="POST",
        )
        if job_id:
            _assert_image_job_runnable(job_id)
        claim_timeout = max(0.1, deadline - time.monotonic()) if deadline is not None else IMAGE_VALIDATION_TIMEOUT_SECONDS
        with _claim_production_resource(
            "audit", job_id or f"character-frame-audit-{uuid4()}", timeout=claim_timeout,
            identity=resource_identity or None,
        ):
            if job_id:
                _assert_image_job_runnable(job_id)
            _require_memory(12 * GIB)
            response_timeout = max(0.1, deadline - time.monotonic()) if deadline is not None else IMAGE_VALIDATION_TIMEOUT_SECONDS
            with urlopen(frame_request, timeout=response_timeout) as response: frame_payload = json.loads(response.read())
        if job_id:
            _assert_image_job_runnable(job_id)
        try:
            frame_verdict = json.loads(str(frame_payload.get("response", "")).strip())
        except json.JSONDecodeError:
            frame_verdict = {}
        verdict["full_head_visible"] = frame_verdict.get("top_of_head_inside_frame") is True
        verdict["feet_visible"] = (
            frame_verdict.get("both_feet_and_shoes_inside_frame") is True
            and frame_verdict.get("full_body_from_head_to_feet_visible") is True
        )
    pose = _face_pose_angles(candidate)
    if target_pose == "left_45_full":
        deterministic_orientation = pose is not None and 30.0 <= pose[1] <= 60.0 and abs(pose[2]) <= 7.0
        verdict["left_45_face_angle_30_to_60"] = deterministic_orientation
    elif target_pose == "right_45_full":
        deterministic_orientation = pose is not None and -60.0 <= pose[1] <= -30.0 and abs(pose[2]) <= 7.0
        verdict["right_45_face_angle_minus_60_to_minus_30"] = deterministic_orientation
    elif target_pose in {"front_full", "front_half"}:
        deterministic_orientation = pose is not None and abs(pose[1]) <= 7.0 and abs(pose[2]) <= 7.0
    elif target_pose == "side_90_full":
        try:
            face_angle = abs(pose[1]) if pose is not None else abs(float(verdict.get("side_face_angle_degrees")))
        except (TypeError, ValueError):
            face_angle = None
        try:
            torso_rotation = abs(float(verdict.get("torso_rotation_degrees")))
        except (TypeError, ValueError):
            torso_rotation = None
        deterministic_orientation = face_angle is not None and 88.0 <= face_angle <= 92.0 and torso_rotation is not None and torso_rotation <= 3.0
        verdict["side_face_angle_degrees"] = face_angle
        verdict["strict_side_face_88_to_92"] = face_angle is not None and 88.0 <= face_angle <= 92.0
        verdict["torso_rotation_degrees"] = torso_rotation
        verdict["torso_rotation_within_3_degrees"] = torso_rotation is not None and torso_rotation <= 3.0
        verdict["side_angle_tier"] = (
            "excellent" if face_angle is not None and 88.0 <= face_angle <= 92.0
            else "borderline_repair" if face_angle is not None and 85.0 <= face_angle <= 95.0
            else "reject"
        )
    elif target_pose == "back_full":
        deterministic_orientation = pose is None
    else:
        deterministic_orientation = True
    verdict["face_pose"] = list(pose) if pose else None
    verdict["deterministic_orientation"] = deterministic_orientation
    verdict["correct_orientation"] = (
        deterministic_orientation
        if target_pose == "front_full"
        else verdict.get("correct_orientation") is True and deterministic_orientation
    )
    if target_pose in {"front_full", "front_half"}:
        try:
            face_similarity = _face_embedding_similarity(reference, candidate, job_id=job_id, deadline=deadline)
        except Exception:
            face_similarity = None
        verdict["face_embedding_similarity"] = face_similarity
        verdict["face_similarity_calibrated_front"] = face_similarity is not None and face_similarity >= 0.35
    try:
        pose_metrics = _pose_proportion_metrics(candidate, job_id=job_id, deadline=deadline) or {}
        head_ratio = _head_body_ratio(candidate, job_id=job_id, deadline=deadline)
    except Exception:
        pose_metrics = {}
        head_ratio = None
    leg_segment_difference = float(pose_metrics.get("thigh_calf_length_difference_percent", -1.0))
    arm_segment_difference = float(pose_metrics.get("upper_lower_arm_length_difference_percent", -1.0))
    torso_lower_limb_ratio = float(pose_metrics.get("torso_to_lower_limb_ratio_percent", -1.0))
    verdict["head_to_body_ratio"] = head_ratio
    verdict.update(pose_metrics)
    verdict["head_to_body_ratio_7_to_7_8"] = head_ratio is not None and 7.0 <= head_ratio <= 7.8
    verdict["thigh_calf_difference_within_8_percent"] = 0.0 <= leg_segment_difference <= 8.0
    verdict["upper_lower_arm_difference_within_10_percent"] = 0.0 <= arm_segment_difference <= 10.0
    verdict["torso_at_least_55_percent_of_lower_limb"] = torso_lower_limb_ratio >= 55.0
    dimensions = _png_dimensions(candidate)
    verdict["pixel_dimensions"] = list(dimensions) if dimensions else None
    verdict["required_928x1664"] = dimensions == (928, 1664)
    deterministic_top_margin, deterministic_bottom_margin, frame_metrics = _verified_character_frame_margins(image)
    if deterministic_top_margin and deterministic_bottom_margin:
        verdict["full_head_visible"] = True
        verdict["feet_visible"] = True
        verdict["top_margin_at_least_8_percent"] = deterministic_top_margin
        verdict["bottom_margin_at_least_3_percent"] = deterministic_bottom_margin
        verdict["frame_validation_source"] = "deterministic_single_person_foreground_normalizer"
    verdict["deterministic_frame_metrics"] = frame_metrics
    if not strict_clothing_reference:
        verdict["exact_clothing_consistent"] = True
        verdict["body_shape_consistent"] = True
    # The first full-body view reveals clothing and body details that do not
    # exist in the accepted headshot. Keep subjective identity/hair/clothing
    # evidence for the mandatory human gate, while automatic admission enforces
    # only facts that can be compared deterministically at this stage. Once the
    # full-body view is confirmed it becomes the strict clothing/body reference
    # for side and back views below.
    verdict["deterministic_full_frame"] = (
        deterministic_top_margin and deterministic_bottom_margin and dimensions == (928, 1664)
    )
    return _character_variant_verdict_passes(verdict, target_pose, bool(strict_clothing_reference)), json.dumps(verdict, ensure_ascii=False)


def _transcribe_media(source: Path) -> str:
    whisper_model = Path("/Users/aoo/AI/Models/Video/LatentSync-1.6/whisper/tiny.pt")
    python = Path("/Users/aoo/AI/Tools/ComfyUI/main/ComfyUI/.venv/bin/python3")
    if not all(path.exists() for path in (FFMPEG, whisper_model, python)):
        raise RuntimeError("本地声音识别组件不完整")
    wav = source.with_suffix(".vision.wav")
    script = """import json,sys,numpy as np,soundfile as sf,whisper
audio,rate=sf.read(sys.argv[1],dtype='float32',always_2d=False)
if getattr(audio,'ndim',1)>1: audio=audio.mean(axis=1)
if rate!=16000: raise RuntimeError(f'采样率异常:{rate}')
model=whisper.load_model('tiny',download_root=sys.argv[2])
result=model.transcribe(np.asarray(audio,dtype=np.float32),language='zh',fp16=False)
print(json.dumps({'text':result.get('text','').strip()},ensure_ascii=False))"""
    try:
        subprocess.run([str(FFMPEG), "-y", "-i", str(source), "-vn", "-ac", "1", "-ar", "16000", str(wav)], check=True, capture_output=True, timeout=600)
        with _claim_production_resource("audio", f"transcribe-{uuid4()}", timeout=1800):
            _require_memory(10 * GIB)
            result = subprocess.run([str(python), "-c", script, str(wav), str(whisper_model.parent)], check=True, capture_output=True, text=True, timeout=1800)
        payload = json.loads(result.stdout.strip().splitlines()[-1])
        return str(payload.get("text", "")).strip()
    finally:
        wav.unlink(missing_ok=True)


def _markdown_project_knowledge() -> str:
    """Load the complete project Markdown knowledge base for each system-agent run."""
    documents: list[str] = []
    for path in sorted(APPLICATION_ROOT.rglob("*.md")):
        relative = path.relative_to(APPLICATION_ROOT)
        if "node_modules" in relative.parts or "dist" in relative.parts or ".git" in relative.parts:
            continue
        try:
            content = path.read_text(encoding="utf-8").strip()
        except (OSError, UnicodeError):
            continue
        documents.append(f"\n\n===== PROJECT MARKDOWN: {relative} =====\n{content}")
    if not documents:
        raise RuntimeError("项目 Markdown 知识库为空")
    return "".join(documents)


def _run_system_agent(agent: str, task: str, context: dict) -> dict:
    specifications = {
        "main_developer": ("主力开发", "main_developer", "workspace-write"),
        "software_tester": ("软件测试", "software-testing", "read-only"),
        "inspector": ("代码稽查", "inspector", "read-only"),
    }
    if agent not in specifications:
        raise ValueError("不支持的系统 AI")
    label, skill_directory, sandbox = specifications[agent]
    if not CODEX_BINARY.exists():
        raise RuntimeError("Codex 执行器不可用")
    skill_prompt = (SYSTEM_AGENT_SKILLS / skill_directory / "system_prompt.md").read_text(encoding="utf-8")
    markdown_knowledge = _markdown_project_knowledge()
    project_context = json.dumps(context, ensure_ascii=False)
    prompt = f"""{skill_prompt}

以下内容是 `/Users/aoo/Code/AI Agent` 当前全部 Markdown 项目知识。你必须在执行任务前完整理解并遵守；先结合全部文档确定项目边界、架构、当前状态、任务顺序和验收规则，再读取代码并执行。文档冲突时以 AGENTS.md、docs/memory/项目记忆.md、当前用户任务的约束顺序裁决，不得使用旧路径或旧任务状态。
{markdown_knowledge}

用户已在项目对话框中明确将下面任务交给你执行。
工作目录固定为：{APPLICATION_ROOT}
当前项目上下文：{project_context}
任务：{task}

必须实际完成授权范围内的工作并验证。最终只汇报结论、变更文件、验证结果和阻塞项。"""
    output_descriptor, output_name = tempfile.mkstemp(prefix=f"{agent}-", suffix=".txt")
    os.close(output_descriptor)
    output_file = Path(output_name)
    try:
        with SYSTEM_AGENT_LOCK:
            result = subprocess.run(
                [str(CODEX_BINARY), "exec", "--ephemeral", "--skip-git-repo-check", "--sandbox", sandbox, "--cd", str(APPLICATION_ROOT), "--output-last-message", str(output_file), prompt],
                cwd=APPLICATION_ROOT,
                capture_output=True,
                text=True,
                timeout=1800,
                check=False,
            )
        reply = output_file.read_text(encoding="utf-8").strip() if output_file.exists() else ""
        if result.returncode != 0:
            detail = (reply or result.stderr or result.stdout).strip().splitlines()[-1:]
            raise RuntimeError(detail[0][:500] if detail else "系统 AI 执行失败")
        if not reply:
            raise RuntimeError("系统 AI 未返回执行结果")
        return {"reply": reply, "agent": label, "execution_mode": sandbox}
    finally:
        output_file.unlink(missing_ok=True)


def _execute_agent_job(job_id: str) -> None:
    with AGENT_JOB_LOCK:
        store = _load_agent_jobs(); job = store.setdefault("jobs", {}).get(job_id)
        if not isinstance(job, dict) or job_id in ACTIVE_AGENT_JOBS: return
        job.update({"status":"running", "started_at":datetime.now(UTC).isoformat(), "heartbeat_at":datetime.now(UTC).isoformat()})
        store["jobs"][job_id] = job; _save_agent_jobs(store); ACTIVE_AGENT_JOBS.add(job_id)
    try:
        result = _run_system_agent(str(job["agent"]), str(job["task"]), dict(job.get("context", {})))
        update = {"status":"completed", "result":result, "finished_at":datetime.now(UTC).isoformat()}
    except Exception as error:
        update = {"status":"failed", "error":str(error)[:500], "finished_at":datetime.now(UTC).isoformat()}
    with AGENT_JOB_LOCK:
        store = _load_agent_jobs(); current = store.setdefault("jobs", {}).get(job_id, {})
        current.update(update); current["heartbeat_at"] = datetime.now(UTC).isoformat()
        store["jobs"][job_id] = current; _save_agent_jobs(store); ACTIVE_AGENT_JOBS.discard(job_id)


def _start_agent_job(job_id: str) -> None:
    threading.Thread(target=_execute_agent_job, args=(job_id,), daemon=True, name=f"system-agent-{job_id[:8]}").start()


def _recover_agent_jobs() -> None:
    with AGENT_JOB_LOCK:
        store = _load_agent_jobs(); recoverable = []
        for job_id, job in store.get("jobs", {}).items():
            if job.get("status") in {"queued", "running"}:
                job["status"] = "queued"; job["recovered_at"] = datetime.now(UTC).isoformat(); recoverable.append(job_id)
        if recoverable: _save_agent_jobs(store)
    for job_id in recoverable: _start_agent_job(job_id)


def _route_system_agent(message: str, context: dict) -> dict:
    text = message.strip()
    recent = context.get("recent_messages", [])
    prior_user = "\n".join(str(item.get("text", "")) for item in recent[-6:] if item.get("role") == "user")
    combined = f"{prior_user}\n{text}".lower()
    tester_terms = ("软件测试", "单元测试", "接口测试", "参数测试", "边界测试", "异常测试", "测试用例", "test")
    inspector_terms = ("检查", "稽查", "审查", "审计", "验收", "验证", "规范", "合规", "问题", "bug", "review", "audit")
    developer_terms = ("开发", "修复", "解决", "整改", "处理", "修改", "实现", "接通", "重构", "新增", "删除", "替换", "运行", "测试", "执行", "写入", "启动")
    project_terms = ("项目", "代码", "文件", ".md", "框架", "系统", "逻辑", "规划", "愿景", "功能", "界面", "对话", "任务", "skill", "api", "前端", "后端", "模型")
    current_requests_change = any(term in text.lower() for term in ("修复", "解决", "整改", "处理", "修改", "实现", "接通", "重构", "新增", "删除", "替换"))
    agent = "main_developer" if current_requests_change else "software_tester" if any(term in combined for term in tester_terms) else "inspector" if any(term in combined for term in inspector_terms) else "main_developer"
    execute = any(term in combined for term in project_terms) and any(term in combined for term in tester_terms + inspector_terms + developer_terms)
    if text.startswith(("@主力开发", "@软件测试", "@代码稽查")):
        execute = True
        agent = "inspector" if text.startswith("@代码稽查") else "software_tester" if text.startswith("@软件测试") else "main_developer"
    return {"execute": execute, "agent": agent, "label": "代码稽查" if agent == "inspector" else "软件测试" if agent == "software_tester" else "主力开发"}


def _safe_name(value: object) -> str:
    cleaned = re.sub(r"[^\w\u4e00-\u9fff.-]+", "_", str(value or "image"), flags=re.UNICODE).strip("._")
    return cleaned[:120] or "image"


def _load_image_jobs() -> dict:
    if not IMAGE_JOBS_FILE.exists():
        return _merge_durable_tasks("image", IMAGE_JOBS_FILE, {"jobs": {}})
    try:
        store = json.loads(IMAGE_JOBS_FILE.read_text(encoding="utf-8"))
        if not isinstance(store, dict):
            return _merge_durable_tasks("image", IMAGE_JOBS_FILE, {"jobs": {}})
        jobs = store.get("jobs", {})
        if isinstance(jobs, list):
            jobs = {str(item[0]): item[1] for item in jobs if isinstance(item, list) and len(item) == 2 and isinstance(item[1], dict)}
        elif not isinstance(jobs, dict):
            jobs = {}
        store["jobs"] = jobs
        return _merge_durable_tasks("image", IMAGE_JOBS_FILE, store)
    except (OSError, json.JSONDecodeError):
        return _merge_durable_tasks("image", IMAGE_JOBS_FILE, {"jobs": {}})


def _save_image_jobs(store: dict) -> None:
    _sync_durable_tasks("image", IMAGE_JOBS_FILE, store)
    atomic_write_json(IMAGE_JOBS_FILE, store, prefix="image-jobs-")


def _comfy_json(path: str, payload: dict | None = None, timeout: int = 10) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    request = Request(
        f"{COMFY_API}{path}", data=data,
        headers={"Content-Type": "application/json"} if data is not None else {},
        method="POST" if data is not None else "GET",
    )
    with urlopen(request, timeout=timeout) as response:
        raw = response.read()
    return json.loads(raw) if raw else {}


def _comfy_prompt_queue_details(prompt_id: object) -> tuple[str, bool]:
    prompt = str(prompt_id or "").strip()
    if not prompt:
        return "absent", False
    queue = _comfy_json("/queue")
    running_ids = {str(item[1]) for item in queue.get("queue_running", []) if isinstance(item, list) and len(item) > 1}
    pending_ids = {str(item[1]) for item in queue.get("queue_pending", []) if isinstance(item, list) and len(item) > 1}
    if prompt in running_ids:
        return "running", bool(running_ids - {prompt})
    if prompt in pending_ids:
        return "pending", bool(running_ids)
    return "absent", bool(running_ids)


def _comfy_prompt_queue_state(prompt_id: object) -> str:
    return _comfy_prompt_queue_details(prompt_id)[0]


def _cancel_comfy_prompt(prompt_id: object, *, confirm_seconds: float = 10.0) -> bool:
    """Cancel one owned prompt and return only after queue disappearance is confirmed."""
    prompt = str(prompt_id or "").strip()
    if not prompt:
        return True
    deadline = time.monotonic() + max(0.0, confirm_seconds)
    while True:
        try:
            state, foreign_running = _comfy_prompt_queue_details(prompt)
            if state == "absent":
                return True
            if state == "pending":
                _comfy_json("/queue", {"delete": [prompt]})
            elif state == "running" and not foreign_running:
                _comfy_json("/interrupt", {})
        except Exception:
            state = "unknown"
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.25)


def _cancel_job_comfy_prompts(job: dict, *, confirm_seconds: float = 10.0) -> bool:
    confirmed = True
    for key in ("schnell_prompt_id", "qwen_prompt_id", "context_ir_prompt_id", "comfy_prompt_id", "validation_prompt_id"):
        prompt_id = str(job.get(key) or "").strip()
        if prompt_id and not _cancel_comfy_prompt(prompt_id, confirm_seconds=confirm_seconds):
            confirmed = False
    return confirmed


def _wait_for_video_comfy_prompts(job_id: str, prompt_ids: list[str]) -> None:
    owned = list(dict.fromkeys(prompt_id for prompt_id in prompt_ids if prompt_id))
    if not owned:
        return
    with VIDEO_JOB_LOCK:
        ACTIVE_VIDEO_PROMPT_CANCELLERS.add(job_id)
    attempts = 0
    try:
        while owned:
            attempts += 1
            remaining = [prompt_id for prompt_id in owned if not _cancel_comfy_prompt(prompt_id, confirm_seconds=5.0)]
            if not remaining:
                return
            _update_video_job(
                job_id, status="generating", stage="cancel_pending", heartbeat_at=_iso_now(),
                cancel_attempts=attempts, cancel_prompt_ids=remaining,
                error="已请求停止，所属Comfy prompt尚未退出；资源票据继续保留并由看门狗监督",
            )
            owned = remaining
            time.sleep(min(5.0, 0.5 * attempts))
    finally:
        with VIDEO_JOB_LOCK:
            ACTIVE_VIDEO_PROMPT_CANCELLERS.discard(job_id)


def _cleanup_comfy_temp_inputs(max_age_seconds: int = 3600) -> int:
    removed = 0
    cutoff = time.time() - max_age_seconds
    for prefix in COMFY_TEMP_PREFIXES:
        directory = COMFY_INPUT / prefix
        if not directory.is_dir():
            continue
        for target in directory.iterdir():
            try:
                if target.is_file() and target.stat().st_mtime < cutoff:
                    target.unlink(missing_ok=True); removed += 1
            except OSError:
                continue
    return removed


def _purge_generated_assets(project_id: object, asset_kind: object = "", asset_name: object = "") -> dict:
    """Delete only generated asset media and job state in the requested project scope."""
    project = str(project_id or "").strip()
    kind = str(asset_kind or "").strip()
    name = str(asset_name or "").strip()
    if not re.fullmatch(r"[0-9a-fA-F-]{36}", project):
        raise ValueError("project_id 无效")
    if kind and kind not in {"character", "scene", "prop"}:
        raise ValueError("asset_kind 无效")
    safe_project = _safe_name(project)
    safe_name = _safe_name(name) if name else ""
    image_pattern = re.compile(
        rf"^{re.escape(safe_project)}_[0-9a-fA-F-]{{36}}_"
        rf"(?P<kind>character|scene|prop)_(?P<name>.+?)_(?:baseline|angle_[0-9]+)(?:_retry_[0-9]+)?\.png$"
    )
    removed_files = 0
    image_dir = OUTPUT_ROOT / "images"
    if image_dir.is_dir():
        for target in image_dir.iterdir():
            if not target.is_file():
                continue
            matched = image_pattern.fullmatch(target.name)
            if not matched or (kind and matched.group("kind") != kind) or (safe_name and matched.group("name") != safe_name):
                continue
            target.unlink(missing_ok=True)
            removed_files += 1

    expected_subject = f"{project}:{kind}:{name}" if kind and name else ""
    removed_jobs = 0
    with IMAGE_JOB_LOCK:
        jobs = _load_image_jobs()
        for job_id, job in list(jobs.get("jobs", {}).items()):
            subject_key = str(job.get("subject_key", ""))
            subject_parts = subject_key.split(":", 2)
            in_project = len(subject_parts) == 3 and subject_parts[0] == project
            in_kind = not kind or (in_project and subject_parts[1] == kind)
            in_name = not name or subject_key == expected_subject
            if not (in_project and in_kind and in_name):
                continue
            _cancel_job_comfy_prompts(job)
            _terminate_process_tree(pid=int(job.get("pid") or 0), process_group=int(job.get("process_group") or 0))
            ACTIVE_IMAGE_PROCESSES.pop(job_id, None)
            ACTIVE_IMAGE_JOBS.discard(job_id)
            jobs["jobs"].pop(job_id, None)
            removed_jobs += 1
        for subject_key in list(ACTIVE_IMAGE_SUBJECTS):
            parts = subject_key.split(":", 2)
            if len(parts) == 3 and parts[0] == project and (not kind or parts[1] == kind) and (not name or subject_key == expected_subject):
                ACTIVE_IMAGE_SUBJECTS.pop(subject_key, None)
        _save_image_jobs(jobs)
    return {"removed_files": removed_files, "removed_jobs": removed_jobs}


def _iso_now() -> str:
    return datetime.now(UTC).isoformat()


def _parse_job_time(value: object) -> float:
    try:
        return datetime.fromisoformat(str(value)).timestamp()
    except (TypeError, ValueError):
        return 0.0


def _terminate_process_tree(process: subprocess.Popen[str] | None = None, *, pid: int = 0, process_group: int = 0) -> None:
    resolved_pid = int(pid or (process.pid if process else 0))
    resolved_group = int(process_group or 0)
    if process is not None and not resolved_group:
        try: resolved_group = os.getpgid(process.pid)
        except (OSError, ProcessLookupError): resolved_group = 0
    if resolved_pid <= 1:
        return
    try:
        if resolved_group > 1 and resolved_group != os.getpgrp(): os.killpg(resolved_group, signal.SIGTERM)
        else: os.kill(resolved_pid, signal.SIGTERM)
    except (OSError, ProcessLookupError):
        return
    if process is not None:
        try:
            process.wait(timeout=5)
            return
        except subprocess.TimeoutExpired:
            pass
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        try: os.kill(resolved_pid, 0)
        except (OSError, ProcessLookupError): return
        time.sleep(0.1)
    try:
        if resolved_group > 1 and resolved_group != os.getpgrp(): os.killpg(resolved_group, signal.SIGKILL)
        else: os.kill(resolved_pid, signal.SIGKILL)
    except (OSError, ProcessLookupError):
        pass


def _update_image_job(job_id: str, **updates: object) -> dict:
    with IMAGE_JOB_LOCK:
        store = _load_image_jobs()
        job = store.setdefault("jobs", {}).setdefault(job_id, {})
        current_status = str(job.get("status") or "")
        requested_status = str(updates.get("status") or current_status)
        if current_status in {"failed", "completed"} and requested_status != current_status:
            return dict(job)
        job.update(updates)
        _save_image_jobs(store)
        return dict(job)


def _assert_image_job_runnable(job_id: str) -> None:
    job = _load_image_jobs().get("jobs", {}).get(job_id, {})
    if job.get("status") in {"failed", "completed"}:
        raise RuntimeError(str(job.get("error") or "图片任务已进入终态"))
    started = _parse_job_time(job.get("started_at"))
    hard_timeout = int(job.get("timeout_seconds") or IMAGE_TASK_TIMEOUT_SECONDS) + int(job.get("queue_timeout_seconds") or IMAGE_QUEUE_TIMEOUT_SECONDS)
    if started and time.time() - started > hard_timeout:
        _update_image_job(job_id, status="failed", error="图片任务超过硬截止时间", finished_at=_iso_now(), pid=None, process_group=None)
        raise RuntimeError("图片任务超过硬截止时间")


def _image_service_scope() -> str:
    return hashlib.sha256(str(IMAGE_JOBS_FILE.parent.resolve()).encode()).hexdigest()[:24]


def _run_image_process(job_id: str, command: list[str], *, cwd: str | Path, target: Path, timeout: int = IMAGE_TASK_TIMEOUT_SECONDS, max_attempts: int = 2) -> None:
    last_detail = "图片生成失败"
    for attempt in range(max(1, max_attempts)):
        current = _load_image_jobs().get("jobs", {}).get(job_id, {})
        if current.get("status") == "failed":
            raise RuntimeError(str(current.get("error") or "图片任务已被回收"))
        if attempt:
            _update_image_job(job_id, status="retrying", retry_count=attempt, heartbeat_at=_iso_now(), pid=None, process_group=None)
        target.unlink(missing_ok=True)
        owner_token = uuid4().hex
        service_scope = _image_service_scope()
        supervised_command = [str(Path(sys.executable).resolve()), str(IMAGE_TASK_SUPERVISOR), "--job-id", job_id, "--owner-token", owner_token, "--service-scope", service_scope, "--", *command]
        process_log = tempfile.TemporaryFile(mode="w+", encoding="utf-8")
        process: subprocess.Popen[str] | None = None
        try:
            with IMAGE_JOB_LOCK:
                if IMAGE_SHUTTING_DOWN.is_set():
                    raise RuntimeError("服务正在关闭，拒绝启动新的图片任务")
                preflight_store = _load_image_jobs()
                preflight_job = preflight_store.get("jobs", {}).get(job_id, {})
                if preflight_job.get("status") in {"failed", "completed"}:
                    raise RuntimeError(str(preflight_job.get("error") or "图片任务已进入终态"))
                preflight_started = _parse_job_time(preflight_job.get("started_at"))
                preflight_hard_timeout = int(preflight_job.get("timeout_seconds") or timeout) + int(preflight_job.get("queue_timeout_seconds") or IMAGE_QUEUE_TIMEOUT_SECONDS)
                if preflight_started and time.time() - preflight_started > preflight_hard_timeout:
                    preflight_job.update({"status":"failed", "error":"图片任务超过硬截止时间", "finished_at":_iso_now(), "pid":None, "process_group":None})
                    _save_image_jobs(preflight_store)
                    raise RuntimeError("图片任务超过硬截止时间")
                process = subprocess.Popen(
                    supervised_command, cwd=str(cwd), stdout=process_log, stderr=subprocess.STDOUT,
                    text=True, start_new_session=True,
                )
                process_group = os.getpgid(process.pid)
                ACTIVE_IMAGE_JOBS.add(job_id)
                ACTIVE_IMAGE_PROCESSES[job_id] = process
                store = _load_image_jobs(); job = store.setdefault("jobs", {}).setdefault(job_id, {})
                job.update({"job_id":job_id, "status":"generating", "pid":process.pid, "process_group":process_group,
                            "started_at":job.get("started_at") or _iso_now(), "process_started_at":_iso_now(),
                            "heartbeat_at":_iso_now(), "timeout_seconds":timeout, "retry_count":attempt,
                            "owner_token":owner_token, "supervisor":str(IMAGE_TASK_SUPERVISOR), "output_path":str(target.resolve()),
                            "service_scope":service_scope,
                            "command_sha256":hashlib.sha256("\0".join(command).encode()).hexdigest()})
                _save_image_jobs(store)
        except RuntimeError as error:
            process_log.close()
            _update_image_job(job_id, status="failed", error=str(error),
                              heartbeat_at=_iso_now(), finished_at=_iso_now(), pid=None, process_group=None)
            raise
        except OSError as error:
            process_log.close()
            last_detail = str(error)[:300]
            if process is not None:
                _terminate_process_tree(process)
                with IMAGE_JOB_LOCK:
                    ACTIVE_IMAGE_JOBS.discard(job_id)
                    ACTIVE_IMAGE_PROCESSES.pop(job_id, None)
                try:
                    _update_image_job(job_id, status="failed", error=f"图片任务登记失败：{last_detail}",
                                      heartbeat_at=_iso_now(), finished_at=_iso_now(), pid=None, process_group=None)
                except OSError:
                    pass
                raise RuntimeError(f"图片任务登记失败：{last_detail}") from error
            _update_image_job(job_id, status="retrying" if attempt < max_attempts - 1 else "failed", error=last_detail,
                              heartbeat_at=_iso_now(), finished_at=_iso_now() if attempt >= max_attempts - 1 else None, retry_count=attempt)
            if attempt < max_attempts - 1: continue
            raise RuntimeError(last_detail) from error
        started = time.monotonic(); last_heartbeat = 0.0; timed_out = False
        while process.poll() is None:
            now = time.monotonic()
            if now - started >= timeout:
                timed_out = True; _terminate_process_tree(process); break
            if now - last_heartbeat >= 2:
                _update_image_job(job_id, heartbeat_at=_iso_now(), pid=process.pid, process_group=process_group)
                last_heartbeat = now
            time.sleep(0.25)
        process.wait(); process_log.seek(0); output = process_log.read(); process_log.close()
        with IMAGE_JOB_LOCK:
            ACTIVE_IMAGE_JOBS.discard(job_id)
            ACTIVE_IMAGE_PROCESSES.pop(job_id, None)
        stopped = _load_image_jobs().get("jobs", {}).get(job_id, {})
        if stopped.get("status") == "failed" and stopped.get("error") == "图片任务已停止":
            raise RuntimeError("图片任务已停止")
        last_detail = "图片任务执行超时" if timed_out else (output or "图片生成失败").strip().splitlines()[-1][:300]
        if not timed_out and process.returncode == 0 and target.is_file():
            _update_image_job(job_id, status="processing", heartbeat_at=_iso_now(), pid=None, process_group=None)
            return
        _update_image_job(job_id, status="retrying" if attempt < max_attempts - 1 else "failed", error=last_detail,
                          heartbeat_at=_iso_now(), finished_at=_iso_now() if attempt >= max_attempts - 1 else None,
                          pid=None, process_group=None, retry_count=attempt)
    raise RuntimeError(last_detail)


def _cleanup_invalid_image_tasks() -> None:
    with IMAGE_JOB_LOCK:
        store = _load_image_jobs(); changed = False
        for job_id, job in store.get("jobs", {}).items():
            process = ACTIVE_IMAGE_PROCESSES.get(job_id)
            running = bool(process and process.poll() is None)
            status = str(job.get("status", ""))
            active_current_request = job_id in ACTIVE_IMAGE_SUBJECTS.values()
            if status in {"queued", "generating", "retrying", "processing"} and not running and not active_current_request:
                job.update({"status":"failed", "error":"新任务启动前已回收无实际进程的旧图片任务", "finished_at":_iso_now(),
                            "pid":None, "process_group":None}); changed = True
            elif running and job.get("status") != "generating":
                _terminate_process_tree(process); ACTIVE_IMAGE_PROCESSES.pop(job_id, None); ACTIVE_IMAGE_JOBS.discard(job_id); changed = True
        if changed: _save_image_jobs(store)
    for pid, group, _ in _orphan_image_processes():
        _terminate_process_tree(pid=pid, process_group=group)


def _recover_image_jobs() -> None:
    with IMAGE_JOB_LOCK:
        IMAGE_SHUTTING_DOWN.clear()
        ACTIVE_IMAGE_JOBS.clear(); ACTIVE_IMAGE_SUBJECTS.clear(); ACTIVE_IMAGE_PROCESSES.clear()
        store = _load_image_jobs(); changed = False
        for job_id, job in store.get("jobs", {}).items():
            # A request can die after its persisted status changed but before ComfyUI
            # receives the interrupt. Reconcile every owned prompt, not only active states.
            _cancel_job_comfy_prompts(job)
            if job.get("identity_recovery") == "quarantined_missing_project" and not job.get("identity_recovery_persisted"):
                job["identity_recovery_persisted"] = True
                job["identity_recovered_at"] = _iso_now()
                changed = True
            if job.get("status") == "completed":
                image = job.get("image") if isinstance(job.get("image"), dict) else {}
                output_path = Path(str(job.get("output_path") or ""))
                media_exists = output_path.is_file()
                if not media_exists:
                    try:
                        media_exists = _local_media_path(image.get("url")).is_file()
                    except (FileNotFoundError, ValueError):
                        media_exists = False
                if not media_exists:
                    job.update({"status":"failed", "error":"已完成图片文件缺失，请重新生成", "finished_at":_iso_now(),
                                "pid":None, "process_group":None})
                    changed = True
                continue
            if job.get("status") not in {"queued", "generating", "retrying", "processing"}: continue
            owned = _persisted_image_process(job_id, job)
            if owned: _terminate_process_tree(pid=owned[0], process_group=owned[1])
            job.update({"status":"failed", "error":"服务重启已回收残留图片任务，请重新生成", "finished_at":_iso_now(),
                        "pid":None, "process_group":None})
            changed = True
        if changed: _save_image_jobs(store)
    # ComfyUI may still be consuming a recently copied input while this API is
    # restarted (or while another scoped instance owns the prompt).  Removing
    # every file here races LoadImage and turns a healthy prompt into a ghost
    # failure.  Owned prompt IDs are cancelled above; only genuinely stale
    # unowned inputs are collected during startup.
    _cleanup_comfy_temp_inputs(3600)


def _persisted_image_process(job_id: str, job: dict) -> tuple[int, int, str] | None:
    pid = int(job.get("pid") or 0); expected_group = int(job.get("process_group") or 0)
    owner_token = str(job.get("owner_token") or "")
    if pid <= 1 or expected_group <= 1 or not owner_token:
        return None
    result = subprocess.run(["ps", "-p", str(pid), "-o", "pgid=,command="], capture_output=True, text=True, timeout=10, check=False)
    line = result.stdout.strip(); parts = line.split(maxsplit=1)
    if len(parts) != 2: return None
    actual_group, command = int(parts[0]), parts[1]
    service_scope = str(job.get("service_scope") or "")
    if not service_scope or service_scope != _image_service_scope(): return None
    required = (str(IMAGE_TASK_SUPERVISOR), f"--job-id {job_id}", f"--owner-token {owner_token}", f"--service-scope {service_scope}")
    if actual_group != expected_group or not all(marker in command for marker in required):
        return None
    return pid, actual_group, command


def _orphan_image_processes() -> list[tuple[int, int, str]]:
    result = subprocess.run(["ps", "-axo", "pid=,pgid=,command="], capture_output=True, text=True, timeout=10, check=False)
    orphans: list[tuple[int, int, str]] = []
    jobs = _load_image_jobs().get("jobs", {})
    service_scope = _image_service_scope()
    active_pids = {process.pid for process in ACTIVE_IMAGE_PROCESSES.values() if process.poll() is None}
    for line in str(getattr(result, "stdout", "") or "").splitlines():
        parts = line.strip().split(maxsplit=2)
        if len(parts) != 3: continue
        pid, group, command = int(parts[0]), int(parts[1]), parts[2]
        if pid in active_pids or str(IMAGE_TASK_SUPERVISOR) not in command or f"--service-scope {service_scope}" not in command: continue
        owned = any(
            job.get("status") == "generating"
            and job.get("service_scope") == service_scope
            and f"--job-id {job_id}" in command
            and f"--owner-token {job.get('owner_token', '')}" in command
            for job_id, job in jobs.items() if job.get("owner_token")
        )
        if not owned:
            orphans.append((pid, group, command))
    return orphans


def _monitor_image_jobs() -> None:
    while not IMAGE_WATCHDOG_STOP.wait(IMAGE_WATCHDOG_SECONDS):
        now = time.time()
        with IMAGE_JOB_LOCK:
            store = _load_image_jobs(); changed = False
            for job_id, job in store.get("jobs", {}).items():
                status = str(job.get("status", "")); process = ACTIVE_IMAGE_PROCESSES.get(job_id)
                worker = ACTIVE_IMAGE_WORKERS.get(job_id)
                worker_alive = bool(worker and worker.is_alive())
                running = bool(process and process.poll() is None)
                age = now - _parse_job_time(job.get("heartbeat_at") or job.get("started_at"))
                hard_age = now - _parse_job_time(job.get("started_at"))
                hard_timeout = int(job.get("timeout_seconds") or IMAGE_TASK_TIMEOUT_SECONDS) + int(job.get("queue_timeout_seconds") or IMAGE_QUEUE_TIMEOUT_SECONDS)
                if status in {"generating", "retrying", "processing"} and not running and not worker_alive and age > IMAGE_WATCHDOG_SECONDS * 2:
                    _cancel_job_comfy_prompts(job)
                    job.update({"status":"failed", "error":"看门狗已回收无实际进程的图片任务", "finished_at":_iso_now(), "pid":None, "process_group":None}); changed = True
                elif status == "queued" and age > IMAGE_QUEUE_TIMEOUT_SECONDS:
                    job.update({"status":"failed", "error":"图片任务排队超时", "finished_at":_iso_now()}); changed = True
                elif status in {"queued", "generating", "retrying", "processing"} and hard_age > hard_timeout:
                    if running: _terminate_process_tree(process); ACTIVE_IMAGE_PROCESSES.pop(job_id, None); ACTIVE_IMAGE_JOBS.discard(job_id)
                    job.update({"status":"failed", "error":"图片任务超过硬截止时间", "finished_at":_iso_now(), "pid":None, "process_group":None}); changed = True
                elif running and status != "generating":
                    _terminate_process_tree(process); ACTIVE_IMAGE_PROCESSES.pop(job_id, None); ACTIVE_IMAGE_JOBS.discard(job_id); changed = True
                if job.get("status") in {"completed", "failed"} and not running:
                    for subject_key, active_job_id in list(ACTIVE_IMAGE_SUBJECTS.items()):
                        if active_job_id == job_id: ACTIVE_IMAGE_SUBJECTS.pop(subject_key, None)
            if changed: _save_image_jobs(store)
        for pid, group, _ in _orphan_image_processes():
            _terminate_process_tree(pid=pid, process_group=group)


def _shutdown_image_jobs() -> None:
    with IMAGE_JOB_LOCK:
        IMAGE_SHUTTING_DOWN.set()
        running = list(ACTIVE_IMAGE_PROCESSES.items())
    for _, process in running:
        _terminate_process_tree(process)
    with IMAGE_JOB_LOCK:
        store = _load_image_jobs(); changed = False
        for job_id, job in store.setdefault("jobs", {}).items():
            if job.get("status") in {"queued", "generating", "retrying", "processing"}:
                _cancel_job_comfy_prompts(job)
                job.update({"status":"failed", "error":"服务关闭已回收图片任务", "finished_at":_iso_now(),
                            "heartbeat_at":_iso_now(), "pid":None, "process_group":None}); changed = True
        if changed: _save_image_jobs(store)
        ACTIVE_IMAGE_PROCESSES.clear(); ACTIVE_IMAGE_JOBS.clear(); ACTIVE_IMAGE_SUBJECTS.clear(); ACTIVE_IMAGE_WORKERS.clear()


def _load_video_jobs() -> dict:
    if not VIDEO_JOBS_FILE.exists(): return _merge_durable_tasks("video", VIDEO_JOBS_FILE, {"jobs": {}})
    try: return _merge_durable_tasks("video", VIDEO_JOBS_FILE, json.loads(VIDEO_JOBS_FILE.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError): return _merge_durable_tasks("video", VIDEO_JOBS_FILE, {"jobs": {}})


def _save_video_jobs(store: dict) -> None:
    _sync_durable_tasks("video", VIDEO_JOBS_FILE, store)
    atomic_write_json(VIDEO_JOBS_FILE, store, prefix="video-jobs-")


def _task_status(value: object) -> str:
    status = str(value or "pending")
    if status in {"confirmed", "completed", "waiting_confirmation", "pass", "skipped"}: return "completed"
    if status in {"generating", "running", "auditing", "repairing", "rechecking"}: return "running"
    if status in {"paused", "stopped"}: return "paused"
    if status in {"failed", "error"}: return "failed"
    if status in {"cancelled", "stale"}: return "cancelled"
    return "queued"


def _task_id(key: str) -> int:
    return zlib.crc32(key.encode("utf-8")) & 0x7FFFFFFF


def _project_tasks(tenant_id: str, user_id: str, project_id: str) -> list[dict]:
    project = next((item for item in _load_store().get("projects", []) if item.get("id") == project_id and item.get("tenant_id") == tenant_id and item.get("user_id") == user_id), None)
    if not project: return []
    stage_names = {
        "requirement":"项目需求", "outline":"故事大纲", "script":"生成剧本", "storyboard":"分镜脚本", "assets":"人物场景",
        "shot_images":"镜头画面", "shot_videos":"分镜视频", "merged_episodes":"合并成片", "final_audit":"成片审核", "upscale":"超分降噪", "export":"成果导出",
    }
    result: list[dict] = []
    video_jobs = _load_video_jobs().get("jobs", {})
    now = datetime.now(UTC).isoformat()
    requirement_key = f"project:{project_id}:requirement"
    result.append({"id":_task_id(requirement_key), "operation_key":requirement_key, "request_id":requirement_key, "label":"项目需求", "status":"completed", "project_id":project_id, "stage":"requirement", "episode":None, "scope_id":project_id, "position":0, "queued_at":project.get("created_at", now), "started_at":project.get("created_at"), "finished_at":project.get("updated_at"), "error":None, "has_result":True})
    for position, (stage, label) in enumerate(stage_names.items(), 1):
        if stage == "requirement": continue
        record = project.get("stage_state", {}).get(stage)
        data = record.get("data", {}) if isinstance(record, dict) else {}
        status = _task_status(data.get("status", "pending"))
        error_text = str(data.get("error", "") or "")
        key = f"project:{project_id}:{stage}"
        result.append({"id":_task_id(key), "operation_key":key, "request_id":key, "label":label, "status":status, "project_id":project_id, "stage":stage, "episode":None, "scope_id":project_id, "position":position, "queued_at":record.get("updated_at", project.get("created_at", now)) if isinstance(record, dict) else project.get("created_at", now), "started_at":record.get("updated_at") if isinstance(record, dict) and status == "running" else None, "finished_at":record.get("updated_at") if isinstance(record, dict) and status in {"completed", "failed"} else None, "error":{"name":"TaskError", "code":"stage_failed", "message":error_text} if error_text else None, "has_result":status == "completed"})
        if stage in {"shot_images", "shot_videos"}:
            for item in data.get("items", []) if isinstance(data.get("items"), list) else []:
                episode, shot = int(item.get("episode", 0) or 0), int(item.get("shot_number", 0) or 0)
                item_status = _task_status(item.get("status"))
                item_error = str(item.get("error", "") or "")
                if stage == "shot_videos":
                    expected_subject = f"{tenant_id}:{user_id}:{project_id}:{episode}:{shot}"
                    candidates = [job for job in video_jobs.values() if isinstance(job, dict) and job.get("subject_key") == expected_subject]
                    live_job = max(candidates, key=lambda job:_parse_job_time(job.get("queued_at"))) if candidates else None
                    if isinstance(live_job, dict):
                        item_status = _task_status(live_job.get("status"))
                        item_error = str(live_job.get("error", "") or item_error)
                item_key = f"project:{project_id}:{stage}:{episode}:{shot}"
                result.append({"id":_task_id(item_key), "operation_key":item_key, "request_id":item_key, "label":f"{label} · 第{episode:02d}集 · 镜头{shot}", "status":item_status, "project_id":project_id, "stage":stage, "episode":episode, "scope_id":str(shot), "position":shot, "queued_at":record.get("updated_at", now), "started_at":record.get("updated_at") if item_status == "running" else None, "finished_at":record.get("updated_at") if item_status in {"completed", "failed"} else None, "error":{"name":"TaskError", "code":"item_failed", "message":item_error} if item_error else None, "has_result":item_status == "completed"})
    return result


def _stop_text_generation(*, stage: str, project_id: str, requested_job_id: str = "", client_generation_id: str = "", identity: dict | None = None) -> tuple[bool, list[str], str]:
    with TEXT_JOB_LOCK:
        store = _load_text_jobs(); targets = []
        for job_id, active in list(ACTIVE_TEXT_JOBS.items()):
            stored = store.get("jobs", {}).get(job_id, {})
            matches = requested_job_id == job_id if requested_job_id else (
                bool(project_id) and active.get("project_id") == project_id and active.get("stage") == stage
                and (not client_generation_id or stored.get("client_generation_id") == client_generation_id)
            )
            if matches and _job_matches_scope(stored, identity): targets.append(job_id)
    owner = _formal_model_owner()
    for job_id in targets: RESOURCE_SCHEDULER.cancel_job(job_id)
    if owner in targets and not _terminate_ollama_model(TEXT_FORMAL_MODEL):
        return False, [], "Ollama推理尚未终止，任务保持运行并由看门狗继续回收"
    stopped = []
    with TEXT_JOB_LOCK:
        for job_id in targets:
            RESOURCE_SCHEDULER.cancel_job(job_id)
            if job_id not in ACTIVE_TEXT_JOBS: continue
            _finish_text_job(job_id, "failed", f"用户停止{'大纲' if stage == 'outline' else '剧本'}生成")
            stopped.append(job_id)
    return True, stopped, ""


def _job_matches_scope(job: dict, identity: dict | None) -> bool:
    if not identity:
        return True
    expected = tuple(str(identity.get(key) or "").strip() for key in ("tenant_id", "user_id", "project_id"))
    if not all(expected):
        return False
    request = job.get("request") if isinstance(job.get("request"), dict) else {}
    actual = tuple(str(job.get(key) or request.get(key) or "").strip() for key in ("tenant_id", "user_id", "project_id"))
    if all(actual):
        return actual == expected
    return str(job.get("subject_key") or "").startswith(":".join(expected) + ":")


def _stop_image_generation(*, project_id: str, requested_name: str = "", stop_all: bool = False, identity: dict | None = None) -> list[str]:
    with IMAGE_JOB_LOCK:
        store = _load_image_jobs(); nonterminal = {"queued", "generating", "retrying", "processing"}
        if requested_name in store.get("jobs", {}) and store["jobs"][requested_name].get("status") in nonterminal and _job_matches_scope(store["jobs"][requested_name], identity):
            targets = [requested_name]
        elif requested_name:
            matches = [(job_id, job) for job_id, job in store.get("jobs", {}).items() if job.get("request_name") == requested_name and job.get("status") in nonterminal and _job_matches_scope(job, identity)]
            targets = [max(matches, key=lambda pair:_parse_job_time(pair[1].get("started_at")))[0]] if matches else []
        else:
            targets = [job_id for job_id, job in store.get("jobs", {}).items() if stop_all and job.get("status") in nonterminal and _job_matches_scope(job, identity) and (identity is not None or not project_id or str(job.get("subject_key", "")).startswith(project_id + ":"))]
        for job_id in targets:
            process = ACTIVE_IMAGE_PROCESSES.pop(job_id, None)
            if process: _terminate_process_tree(process)
            ACTIVE_IMAGE_JOBS.discard(job_id); job = store["jobs"][job_id]; _cancel_job_comfy_prompts(job)
            job.update({"status":"failed", "error":"图片任务已停止", "finished_at":_iso_now(), "heartbeat_at":_iso_now(), "pid":None, "process_group":None})
            for subject_key, active_job_id in list(ACTIVE_IMAGE_SUBJECTS.items()):
                if active_job_id == job_id: ACTIVE_IMAGE_SUBJECTS.pop(subject_key, None)
        if targets: _save_image_jobs(store)
    return targets


def _stop_video_generation(*, requested_job_id: str = "", subject_key: str = "", identity: dict | None = None) -> list[str]:
    with VIDEO_JOB_LOCK:
        store = _load_video_jobs(); matches = [(job_id, job) for job_id, job in store.get("jobs", {}).items() if job.get("status") in {"waiting_memory", "generating"} and _job_matches_scope(job, identity) and (job_id == requested_job_id or (subject_key and job.get("subject_key") == subject_key))]
        targets = [max(matches, key=lambda pair:_parse_job_time(pair[1].get("queued_at")))] if matches else []
        processes = [(job_id, ACTIVE_VIDEO_PROCESSES.get(job_id)) for job_id, _ in targets]
        for job_id, _ in targets:
            store["jobs"][job_id].update({"cancel_requested_at":_iso_now(), "stage":"cancelling", "heartbeat_at":_iso_now()})
        if targets:
            _save_video_jobs(store)
    for _, process in processes:
        if process: _terminate_process_tree(process)
    confirmed = [(job_id, job) for job_id, job in targets if _cancel_job_comfy_prompts(job)]
    for job_id, _ in confirmed: RESOURCE_SCHEDULER.cancel_job(job_id)
    committed: list[tuple[str, dict]] = []
    for job_id, job in confirmed:
        _commit_video_terminal(job_id, status="cancelled", stage="cancelled", error="视频任务已停止", finished_at=_iso_now(), heartbeat_at=_iso_now(), pid=None, process_group=None)
        committed.append((job_id, job))
    with VIDEO_JOB_LOCK:
        store = _load_video_jobs()
        for job_id, _ in committed:
            job = store["jobs"][job_id]
            ACTIVE_VIDEO_JOBS.discard(job_id); ACTIVE_VIDEO_PROCESSES.pop(job_id, None)
            if ACTIVE_VIDEO_SUBJECTS.get(str(job.get("subject_key"))) == job_id: ACTIVE_VIDEO_SUBJECTS.pop(str(job.get("subject_key")), None)
        for job_id, _ in targets:
            if any(committed_id == job_id for committed_id, _ in committed):
                continue
            store["jobs"][job_id].update({"status":"generating", "stage":"cancel_pending", "error":"停止请求尚未确认所属Comfy prompt退出", "heartbeat_at":_iso_now()})
        if targets: _save_video_jobs(store)
    return [job_id for job_id, _ in committed]


def _resume_persisted_task(body: dict, operation_key: str) -> tuple[bool, str]:
    project_id = str(body.get("project_id") or ""); parts = operation_key.split(":")
    if len(parts) < 3 or parts[:2] != ["project", project_id]: return False, "invalid_operation_key"
    stage = parts[2]; candidates: list[dict] = []
    if stage in {"outline", "script"}:
        candidates = [job for job in _load_text_jobs().get("jobs", {}).values() if job.get("project_id") == project_id and job.get("stage") == stage and job.get("status") == "failed"]
    elif stage in {"shot_images", "assets"}:
        for job in _load_image_jobs().get("jobs", {}).values():
            if job.get("status") not in {"failed", "cancelled"} or not str(job.get("subject_key", "")).startswith(project_id + ":"): continue
            request_payload = job.get("request") if isinstance(job.get("request"), dict) else {}
            if stage == "shot_images" and len(parts) >= 5 and (int(request_payload.get("episode", 0) or 0), int(request_payload.get("shot_number", 0) or 0)) != (int(parts[3]), int(parts[4])): continue
            candidates.append(job)
    elif stage == "shot_videos" and len(parts) >= 5:
        expected = f"{body.get('tenant_id', '')}:{body.get('user_id', '')}:{project_id}:{parts[3]}:{parts[4]}"
        candidates = [job for job in _load_video_jobs().get("jobs", {}).values() if job.get("subject_key") == expected and job.get("status") in {"failed", "cancelled"}]
    if not candidates: return False, "persisted_request_not_found"
    source = max(candidates, key=lambda job:_parse_job_time(job.get("updated_at") or job.get("finished_at") or job.get("queued_at") or job.get("started_at")))
    endpoint = str(source.get("endpoint") or ("/api/videos/generate" if stage == "shot_videos" else ""))
    payload = dict(source.get("request") or {})
    if not endpoint or not payload: return False, "persisted_request_not_found"
    payload["generation_id"] = str(uuid4()); payload.pop("job_id", None)
    threading.Thread(target=_replay_persisted_request, args=(endpoint, payload), daemon=True, name=f"task-resume-{uuid4().hex[:8]}").start()
    return True, endpoint


def _video_key(body: dict) -> str:
    return ":".join(str(body.get(key, "")) for key in ("tenant_id", "user_id", "project_id", "episode", "shot_number"))


def _local_media_path(url: object) -> Path:
    parsed = urlparse(str(url or "")); query = parse_qs(parsed.query)
    filename = Path(query.get("filename", [""])[0]).name
    subfolder = Path(query.get("subfolder", ["images"])[0]).name
    target = (OUTPUT_ROOT / subfolder / filename).resolve()
    if not filename or OUTPUT_ROOT not in target.parents or not target.is_file():
        raise FileNotFoundError("分镜图片不存在")
    return target


def _resolve_media_input(value: object) -> Path:
    raw = str(value or "")
    if raw.startswith("/api/"): return _local_media_path(raw)
    target = Path(raw).resolve()
    allowed = [OUTPUT_ROOT, Path("/Users/aoo/AI/ComfyUI-Shared/output").resolve()]
    if not target.is_file() or not any(root == target or root in target.parents for root in allowed): raise FileNotFoundError("媒体文件不存在")
    return target


def _start_comfy() -> None:
    subprocess.run([str(COMFY_PYTHON), str(START_COMFY)], check=True, capture_output=True, text=True, timeout=120)


def _free_comfy_memory() -> None:
    global LAST_COMFY_FREE_AT
    try:
        request = Request(f"{COMFY_API}/free", data=b'{"unload_models":true,"free_memory":true}', headers={"Content-Type":"application/json"}, method="POST")
        with urlopen(request, timeout=30): pass
        LAST_COMFY_FREE_AT = time.monotonic()
    except Exception:
        pass


def _run_comfy_function(function: str, inputs: list[Path | str], target: Path, prefix: str) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    _start_comfy()
    script = """from pathlib import Path
import shutil,sys
sys.path.insert(0,sys.argv[1])
import comfy_client
function=sys.argv[2]; target=Path(sys.argv[3]); prefix=sys.argv[4]
if function == 'tts':
    result=comfy_client.tts(sys.argv[5],prefix,speaker=sys.argv[6],instruct=sys.argv[7])
elif function == 'musetalk':
    result=comfy_client.musetalk(Path(sys.argv[5]),Path(sys.argv[6]),prefix)
elif function == 'image_upscale':
    result=comfy_client.upscale_image_1080p(Path(sys.argv[5]),prefix)
elif function == 'video_upscale_interpolate':
    result=comfy_client.upscale_video_720p(Path(sys.argv[5]),prefix,fps=int(sys.argv[6]))
else:
    raise RuntimeError('unsupported media function')
shutil.copy2(result,target)
"""
    subprocess.run([str(COMFY_PYTHON), "-c", script, str(PIPELINE_ROOT), function, str(target), prefix, *map(str, inputs)], check=True, capture_output=True, text=True, timeout=14400)
    if not target.is_file(): raise RuntimeError("媒体模型未生成输出文件")
    return target


def _pulid_identity_refine(source: Path, face_reference: Path, target: Path, prefix: str) -> Path:
    source_name = f"short_drama_pulid/{uuid4().hex}{source.suffix.lower()}"
    face_name = f"short_drama_pulid/{uuid4().hex}{face_reference.suffix.lower()}"
    for origin, name in ((source, source_name), (face_reference, face_name)):
        destination = COMFY_INPUT / name; destination.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(origin, destination)
    graph = {
        "1":{"class_type":"UnetLoaderGGUF","inputs":{"unet_name":"flux1-schnell-Q8_0.gguf"}},
        "2":{"class_type":"DualCLIPLoader","inputs":{"clip_name1":"clip_l.safetensors","clip_name2":"t5xxl_fp8_e4m3fn_scaled.safetensors","type":"flux"}},
        "3":{"class_type":"LoadImage","inputs":{"image":face_name}}, "4":{"class_type":"LoadImage","inputs":{"image":source_name}},
        "5":{"class_type":"PulidFluxModelLoader","inputs":{"pulid_file":"pulid_flux_v0.9.1.safetensors"}},
        "6":{"class_type":"PulidFluxFaceNetLoader","inputs":{"provider":"CPU"}}, "7":{"class_type":"PulidFluxEvaClipLoader","inputs":{}},
        "8":{"class_type":"ApplyPulidFlux","inputs":{"model":["1",0],"pulid_flux":["5",0],"eva_clip":["7",0],"face_analysis":["6",0],"image":["3",0],"weight":0.72,"start_at":0.0,"end_at":0.80}},
        "9":{"class_type":"ModelSamplingFlux","inputs":{"model":["8",0],"max_shift":1.15,"base_shift":0.5,"width":768,"height":1344}},
        "10":{"class_type":"CLIPTextEncode","inputs":{"clip":["2",0],"text":"preserve exact pose, clothing, composition and background; refine only the same person's facial identity"}},
        "11":{"class_type":"VAELoader","inputs":{"vae_name":"ae.safetensors"}}, "12":{"class_type":"VAEEncode","inputs":{"pixels":["4",0],"vae":["11",0]}},
        "13":{"class_type":"KSampler","inputs":{"model":["9",0],"seed":int(time.time_ns()%2**32),"steps":8,"cfg":1.0,"sampler_name":"euler","scheduler":"simple","positive":["10",0],"negative":["10",0],"latent_image":["12",0],"denoise":0.28}},
        "14":{"class_type":"VAEDecode","inputs":{"samples":["13",0],"vae":["11",0]}}, "15":{"class_type":"SaveImage","inputs":{"images":["14",0],"filename_prefix":prefix}},
    }
    prompt_id = _comfy_json("/prompt", {"prompt":graph}, timeout=30)["prompt_id"]
    try:
        deadline=time.time()+900
        while time.time()<deadline:
            time.sleep(2); record=_comfy_json(f"/history/{prompt_id}", timeout=30).get(prompt_id)
            if not record: continue
            if record.get("status",{}).get("status_str") != "success": raise RuntimeError("PuLID身份修正失败")
            media=record["outputs"]["15"]["images"][0]; target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(COMFY_OUTPUT / media.get("subfolder","") / media["filename"], target); return target
        raise TimeoutError("PuLID身份修正超时")
    finally:
        _cancel_comfy_prompt(prompt_id)
        (COMFY_INPUT/source_name).unlink(missing_ok=True); (COMFY_INPUT/face_name).unlink(missing_ok=True); _free_comfy_memory()


def _media_duration(path: Path) -> float:
    result = subprocess.run([str(FFMPEG), "-hide_banner", "-i", str(path)], capture_output=True, text=True, timeout=60)
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", result.stderr)
    if not match: raise RuntimeError("无法读取媒体时长")
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def _has_audio_stream(path: Path) -> bool:
    result = subprocess.run([str(FFMPEG), "-hide_banner", "-i", str(path)], capture_output=True, text=True, timeout=60)
    return bool(re.search(r"Stream #\S+.*Audio:", result.stderr))


def _media_url(path: Path) -> str:
    relative = path.resolve().relative_to(OUTPUT_ROOT)
    version = path.stat().st_mtime_ns if path.exists() else time.time_ns()
    return f"/api/result-media?filename={relative.name}&subfolder={relative.parent.as_posix()}&v={version}"


def _run_ffmpeg(arguments: list[str], target: Path, timeout: int = 1800) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run([str(FFMPEG), "-y", *arguments, str(target)], capture_output=True, text=True, timeout=timeout, check=False)
    if result.returncode != 0 or not target.is_file() or target.stat().st_size == 0:
        detail = (result.stderr or result.stdout or "FFmpeg 处理失败").strip().splitlines()[-1]
        raise RuntimeError(detail[:500])
    return target


def _generate_bgm(duration: float, target: Path) -> Path:
    """Create a deterministic, license-free four-chord ambient score."""
    seconds = max(1.0, duration)
    fade_out = max(0.0, seconds - min(2.0, seconds / 2))
    chords = (
        (130.81, 261.63, 329.63, 392.00),
        (110.00, 220.00, 261.63, 329.63),
        (87.31, 174.61, 220.00, 261.63),
        (98.00, 196.00, 246.94, 293.66),
    )
    arguments: list[str] = []
    filters: list[str] = []
    input_index = 0
    for chord_index, chord in enumerate(chords):
        labels: list[str] = []
        for frequency in chord:
            arguments.extend(["-f", "lavfi", "-i", f"sine=frequency={frequency}:sample_rate=48000:duration=4"])
            labels.append(f"[{input_index}:a]")
            input_index += 1
        filters.append(f"{''.join(labels)}amix=inputs=4:normalize=0,volume=0.035,afade=t=in:st=0:d=0.35,afade=t=out:st=3.65:d=0.35[c{chord_index}]")
    filters.append(
        f"[c0][c1][c2][c3]concat=n=4:v=0:a=1,aloop=loop=-1:size=768000,atrim=duration={seconds:.3f},"
        f"lowpass=f=1600,afade=t=in:st=0:d={min(2.0, seconds / 2):.3f},"
        f"afade=t=out:st={fade_out:.3f}:d={min(2.0, seconds / 2):.3f}[music]"
    )
    return _run_ffmpeg([*arguments, "-filter_complex", ";".join(filters), "-map", "[music]", "-c:a", "aac", "-b:a", "192k"], target)


def _mix_bgm(source: Path, bgm: Path, target: Path, bgm_volume: float) -> Path:
    volume = max(0.0, min(1.0, bgm_volume))
    duration = _media_duration(source)
    if _has_audio_stream(source):
        arguments = [
            "-i", str(source), "-stream_loop", "-1", "-i", str(bgm),
            "-filter_complex", f"[0:a]volume=2.0[voice];[1:a]volume={volume:.3f}[music];[music][voice]sidechaincompress=threshold=0.015:ratio=10:attack=15:release=450[ducked];[voice][ducked]amix=inputs=2:duration=first:dropout_transition=2:normalize=0[a]",
            "-map", "0:v:0", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-t", f"{duration:.3f}",
        ]
    else:
        arguments = [
            "-i", str(source), "-stream_loop", "-1", "-i", str(bgm),
            "-filter_complex", f"[1:a]volume={volume:.3f}[a]", "-map", "0:v:0", "-map", "[a]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-t", f"{duration:.3f}",
        ]
    return _run_ffmpeg(arguments, target)


def _attach_dialogue_audio(video: Path, audio: Path, target: Path) -> Path:
    return _run_ffmpeg([
        "-i", str(video), "-i", str(audio), "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest",
    ], target)


def _normalize_shot_media(video: Path, audio: Path | None, target: Path) -> Path:
    """Produce concat-safe H.264/AAC media while preserving the shot duration."""
    duration = _media_duration(video)
    if audio is not None:
        audio_arguments = ["-i", str(audio), "-filter_complex", f"[1:a]apad,atrim=duration={duration:.3f}[a]", "-map", "0:v:0", "-map", "[a]"]
    else:
        audio_arguments = ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono", "-filter_complex", f"[1:a]atrim=duration={duration:.3f}[a]", "-map", "0:v:0", "-map", "[a]"]
    return _run_ffmpeg([
        "-i", str(video), *audio_arguments, "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-pix_fmt", "yuv420p", "-r", str(PRODUCTION_FRAME_RATE), "-c:a", "aac", "-ar", "48000", "-b:a", "192k", "-t", f"{duration:.3f}",
    ], target)


def _subtitle_timestamp(seconds: object) -> str:
    milliseconds = max(0, int(float(seconds or 0) * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000); minutes, remainder = divmod(remainder, 60_000); secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _write_srt(subtitles: list[dict], directory: Path) -> Path:
    target = directory / "subtitles.srt"
    lines: list[str] = []
    for index, item in enumerate(subtitles, 1):
        lines.extend([str(index), f"{_subtitle_timestamp(item.get('start'))} --> {_subtitle_timestamp(item.get('end'))}", str(item.get("text", "")).replace("\n", " "), ""])
    target.write_text("\n".join(lines), encoding="utf-8")
    return target


def _burn_subtitles(source: Path, subtitles: list[dict], target: Path) -> Path:
    if not subtitles:
        shutil.copy2(source, target); return target
    with tempfile.TemporaryDirectory(prefix="short-drama-subtitles-") as temporary:
        srt = _write_srt(subtitles, Path(temporary))
        escaped = str(srt).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
        return _run_ffmpeg(["-i", str(source), "-vf", f"subtitles='{escaped}'", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-c:a", "copy"], target)


def _run_latentsync(video: Path, audio: Path, target: Path, steps: int) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    command = [str(COMFY_PYTHON), "-m", "scripts.inference", "--unet_config_path", "configs/unet/stage2_512.yaml", "--inference_ckpt_path", str(LATENTSYNC_MODELS / "latentsync_unet.pt"), "--inference_steps", str(max(1, min(30, steps))), "--guidance_scale", "1.5", "--video_path", str(video), "--audio_path", str(audio), "--video_out_path", str(target)]
    subprocess.run(command, cwd=LATENTSYNC_ROOT, env={**os.environ, "PATH": f"{LATENTSYNC_ROOT / 'bin'}:{os.environ.get('PATH', '')}", "LATENTSYNC_WHISPER_MODEL": str(LATENTSYNC_MODELS / "whisper/tiny.pt"), "LATENTSYNC_VAE_MODEL": str(LATENTSYNC_MODELS / "vae")}, check=True, capture_output=True, text=True, timeout=14400)
    if not target.is_file(): raise RuntimeError("LatentSync 未生成输出文件")
    return target


def _update_video_job(job_id: str, **changes: object) -> dict:
    with VIDEO_JOB_LOCK:
        store = _load_video_jobs(); job = store.setdefault("jobs", {}).setdefault(job_id, {})
        if job.get("status") in {"completed", "failed", "cancelled"} and changes.get("status") not in {None, job.get("status")}:
            return dict(job)
        job.update(changes); _save_video_jobs(store); return dict(job)


def _video_job_stopping(job: dict) -> bool:
    return job.get("status") in {"cancelled", "failed"} or bool(job.get("cancel_requested_at"))


def _commit_video_terminal(job_id: str, *, status: str, stage: str, **changes: object) -> dict:
    current = _load_video_jobs().get("jobs", {}).get(job_id, {})
    prompt_ids = [str(current.get(key) or "").strip() for key in ("context_ir_prompt_id", "comfy_prompt_id")]
    _wait_for_video_comfy_prompts(job_id, prompt_ids)
    committed = _update_video_job(job_id, status=status, stage=stage, **changes)
    prompt_ids = [str(committed.get(key) or "").strip() for key in ("context_ir_prompt_id", "comfy_prompt_id")]
    _wait_for_video_comfy_prompts(job_id, prompt_ids)
    return committed


def _context_ir_history_text(record: dict, node_id: str) -> str:
    output = record.get("outputs", {}).get(node_id, {}) if isinstance(record, dict) else {}
    for key in ("text", "string", "value"):
        value = output.get(key) if isinstance(output, dict) else None
        if isinstance(value, list):
            value = value[0] if value else ""
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


class _ContextIRPersistenceError(RuntimeError):
    """A durable-output failure that must never trigger another heavy inference."""


def _persist_h3_context_ir_outputs(job_id: str, optimized_prompt: str, selected_skills: str, raw_json: str) -> dict:
    if not optimized_prompt.strip() or not selected_skills.strip() or not raw_json.strip():
        raise RuntimeError("H3 Context IR输出不完整")
    job_root = H3_CONTEXT_IR_OUTPUT_ROOT / _safe_name(job_id)
    job_root.mkdir(parents=True, exist_ok=True)
    publication_id = uuid4().hex
    staging_dir = job_root / f".{publication_id}.staging"
    output_dir = job_root / publication_id
    staging_dir.mkdir()
    values = {
        "optimized_prompt": (optimized_prompt.strip(), ".txt"),
        "selected_skills": (selected_skills.strip(), ".json"),
        "raw_json": (raw_json.strip(), ".json"),
    }
    try:
        filenames: dict[str, str] = {}
        for key, (value, suffix) in values.items():
            filename = f"{key}{suffix}"
            (staging_dir / filename).write_text(value, encoding="utf-8")
            filenames[key] = filename
        # The completed three-file set becomes visible in one filesystem step.
        os.replace(staging_dir, output_dir)
        return {key:str(output_dir / filename) for key, filename in filenames.items()}
    finally:
        if staging_dir.exists():
            shutil.rmtree(staging_dir, ignore_errors=True)


def _optimize_h3_ref2va_prompt(job_id: str, body: dict, *, duration: int, prompt: str) -> str:
    """Run Context IR as a standalone persisted stage before H3 is loaded."""
    if not prompt.strip():
        raise RuntimeError("H3 Context IR缺少原始提示词")
    identity_reference = _resolve_media_input(body.get("identity_reference_url"))
    identity_name = f"short_drama_h3_context_ir/{uuid4().hex}{identity_reference.suffix.lower()}"
    identity_input = COMFY_INPUT / identity_name
    frames = max(5, round(duration * 24))
    frames += (5 - frames % 17) % 17
    prefix_root = f"h3_context_ir/{_safe_name(job_id)}_{uuid4().hex[:8]}"
    prompt_ids: list[str] = []
    saved_files: list[Path] = []
    uncommitted_publication_dirs: list[Path] = []
    result: tuple[str, str, str] | None = None
    try:
        _start_comfy()
        identity_input.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(identity_reference, identity_input)
        for attempt in range(2):
            current = _load_video_jobs().get("jobs", {}).get(job_id, {})
            if _video_job_stopping(current):
                raise RuntimeError(str(current.get("error") or "视频任务已停止"))
            graph = {
                "1":{"class_type":"LoadImage","inputs":{"image":identity_name}},
                "2":{"class_type":"MiniMaxH3Ref2VAPromptAgentOpenAIAPI","inputs":{
                    "prompt":prompt,"length":frames,"ref_images":{"ref_image_0":["1",0]},
                    "model":"custom","custom_model":H3_CONTEXT_IR_MODEL,"reasoning_effort":"medium","api_mode":"responses",
                }},
                "3":{"class_type":"SaveText","inputs":{"text":["2",0],"filename_prefix":f"{prefix_root}_optimized_a{attempt + 1}","format":"txt"}},
                "4":{"class_type":"SaveText","inputs":{"text":["2",1],"filename_prefix":f"{prefix_root}_skills_a{attempt + 1}","format":"json"}},
                "5":{"class_type":"SaveText","inputs":{"text":["2",2],"filename_prefix":f"{prefix_root}_raw_a{attempt + 1}","format":"json"}},
            }
            prompt_id = ""
            try:
                prompt_id = str(_comfy_json("/prompt", {"prompt":graph}, timeout=30)["prompt_id"])
                prompt_ids.append(prompt_id)
                _update_video_job(
                    job_id, status="generating", stage="h3_context_ir", context_ir_stage="optimizing",
                    context_ir_prompt_id=prompt_id, comfy_prompt_id=prompt_id, context_ir_attempt=attempt + 1,
                    context_ir_started_at=_iso_now(), heartbeat_at=_iso_now(),
                )
                deadline = time.time() + H3_CONTEXT_IR_TIMEOUT_SECONDS
                history_errors = 0
                while time.time() < deadline:
                    current = _load_video_jobs().get("jobs", {}).get(job_id, {})
                    if _video_job_stopping(current):
                        raise RuntimeError(str(current.get("error") or "视频任务已停止"))
                    try:
                        record = _comfy_json(f"/history/{prompt_id}", timeout=30).get(prompt_id)
                    except Exception:
                        history_errors += 1
                        if history_errors > 1:
                            raise RuntimeError("H3 Context IR历史查询异常")
                        time.sleep(1)
                        continue
                    if record:
                        status = record.get("status", {})
                        if status.get("status_str") == "error":
                            raise RuntimeError("H3 Context IR执行失败")
                        if status.get("status_str") == "success":
                            optimized = _context_ir_history_text(record, "3")
                            skills = _context_ir_history_text(record, "4")
                            raw = _context_ir_history_text(record, "5")
                            if not all((optimized, skills, raw)):
                                patterns = {
                                    "optimized": f"{prefix_root}_optimized_a{attempt + 1}*.txt",
                                    "skills": f"{prefix_root}_skills_a{attempt + 1}*.json",
                                    "raw": f"{prefix_root}_raw_a{attempt + 1}*.json",
                                }
                                files = {key:sorted(COMFY_OUTPUT.glob(pattern), key=lambda path:path.stat().st_mtime, reverse=True) for key, pattern in patterns.items()}
                                saved_files.extend(path for matches in files.values() for path in matches)
                                optimized = optimized or (files["optimized"][0].read_text(encoding="utf-8").strip() if files["optimized"] else "")
                                skills = skills or (files["skills"][0].read_text(encoding="utf-8").strip() if files["skills"] else "")
                                raw = raw or (files["raw"][0].read_text(encoding="utf-8").strip() if files["raw"] else "")
                            if not all((optimized, skills, raw)):
                                raise RuntimeError("H3 Context IR未返回完整优化结果")
                            paths = _persist_h3_context_ir_outputs(job_id, optimized, skills, raw)
                            try:
                                source_paths = {
                                    key:Path(paths[key])
                                    for key in ("optimized_prompt", "selected_skills", "raw_json")
                                }
                                declared_job_root = Path(os.path.abspath(H3_CONTEXT_IR_OUTPUT_ROOT / _safe_name(job_id)))
                                declared_paths = {key:Path(os.path.abspath(path)) for key, path in source_paths.items()}
                                publication_dirs_declared = {path.parent for path in declared_paths.values()}
                                if (
                                    len(publication_dirs_declared) != 1
                                    or next(iter(publication_dirs_declared)).parent != declared_job_root
                                    or declared_job_root.is_symlink()
                                    or next(iter(publication_dirs_declared)).is_symlink()
                                    or any(path.is_symlink() for path in declared_paths.values())
                                ):
                                    raise ValueError("persisted output path components must be one non-symlink publication")
                                resolved = {
                                    key:path.resolve(strict=True) for key, path in declared_paths.items()
                                }
                                publication_dirs = {path.parent for path in resolved.values()}
                                expected_job_root = (H3_CONTEXT_IR_OUTPUT_ROOT / _safe_name(job_id)).resolve(strict=True)
                                if len(publication_dirs) != 1 or next(iter(publication_dirs)).parent != expected_job_root:
                                    raise ValueError("persisted outputs are not one current-job publication")
                                if not all(path.is_file() for path in resolved.values()):
                                    raise ValueError("persisted output is not a regular file")
                                publication_dir = next(iter(publication_dirs))
                                uncommitted_publication_dirs.append(publication_dir)
                                persisted_optimized = resolved["optimized_prompt"].read_text(encoding="utf-8").strip()
                                persisted_skills = resolved["selected_skills"].read_text(encoding="utf-8").strip()
                                persisted_raw = resolved["raw_json"].read_text(encoding="utf-8").strip()
                                if not all((persisted_optimized, persisted_skills, persisted_raw)):
                                    raise ValueError("empty persisted output")
                                json.loads(persisted_skills)
                                json.loads(persisted_raw)
                            except (KeyError, OSError, ValueError, json.JSONDecodeError) as error:
                                raise _ContextIRPersistenceError("H3 Context IR持久输出不可用") from error
                            _update_video_job(
                                job_id, stage="h3_context_ir", context_ir_stage="completed", context_ir_prompt_id=prompt_id,
                                comfy_prompt_id=prompt_id, optimized_prompt=persisted_optimized,
                                context_ir_selected_skills=persisted_skills, context_ir_raw_json=persisted_raw,
                                context_ir_outputs=paths, context_ir_finished_at=_iso_now(), heartbeat_at=_iso_now(),
                            )
                            uncommitted_publication_dirs.remove(publication_dir)
                            result = (persisted_optimized, persisted_skills, persisted_raw)
                            break
                    _update_video_job(job_id, stage="h3_context_ir", context_ir_stage="optimizing", heartbeat_at=_iso_now())
                    time.sleep(2)
                if result:
                    break
                if time.time() >= deadline:
                    raise TimeoutError("H3 Context IR超过硬截止时间")
            except (TimeoutError, OSError, _ContextIRPersistenceError):
                raise
            except Exception:
                current = _load_video_jobs().get("jobs", {}).get(job_id, {})
                if _video_job_stopping(current) or attempt >= 1:
                    raise
                _update_video_job(job_id, stage="h3_context_ir", context_ir_stage="retrying", context_ir_attempt=2, heartbeat_at=_iso_now())
            finally:
                if prompt_id:
                    _wait_for_video_comfy_prompts(job_id, [prompt_id])
        if result is None:
            raise RuntimeError("H3 Context IR未生成优化提示词")
    finally:
        _wait_for_video_comfy_prompts(job_id, prompt_ids)
        try:
            identity_input.unlink(missing_ok=True)
        except OSError:
            pass
        try:
            identity_input.parent.rmdir()
        except OSError:
            pass
        owned_intermediates = set(saved_files)
        try:
            owned_intermediates.update(path for path in COMFY_OUTPUT.glob(f"{prefix_root}_*") if path.is_file())
        except OSError:
            pass
        for path in owned_intermediates:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
        for path in uncommitted_publication_dirs:
            shutil.rmtree(path, ignore_errors=True)
        unloaded = _terminate_ollama_model(H3_CONTEXT_IR_MODEL)
        _free_comfy_memory()
        if not unloaded or _ollama_model_loaded(H3_CONTEXT_IR_MODEL):
            raise RuntimeError("H3 Context IR模型未卸载，已阻断H3视频推理")
    return result[0]


def _generate_h3_rv2v_video(job_id: str, body: dict, target: Path, *, duration: int, optimized_prompt: str) -> Path:
    """Render one shot with local MiniMax H3 Ref2VA.

    Blender video is the geometry/camera reference and the approved 2D portrait
    is the identity reference.  Both remain independent files and are joined
    only by the H3 graph.
    """
    current = _load_video_jobs().get("jobs", {}).get(job_id, {})
    if _video_job_stopping(current):
        raise RuntimeError(str(current.get("error") or "视频任务已停止"))
    source_video = _resolve_media_input(body.get("source_video_url"))
    identity_reference = _resolve_media_input(body.get("identity_reference_url"))
    required = {
        COMFY_OUTPUT.parent / "models/diffusion_models" / H3_REF2VA_MODEL,
        COMFY_OUTPUT.parent / "models/text_encoders" / H3_TEXT_ENCODER,
        COMFY_OUTPUT.parent / "models/vae" / H3_VIDEO_VAE,
        COMFY_OUTPUT.parent / "models/vae" / H3_AUDIO_VAE,
    }
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise RuntimeError(f"H3本地模型不完整：{', '.join(missing)}")
    _start_comfy()
    identity_name = f"short_drama_h3/{uuid4().hex}{identity_reference.suffix.lower()}"
    identity_input = COMFY_INPUT / identity_name
    identity_input.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(identity_reference, identity_input)
    frames = max(5, round(duration * 24))
    frames += (5 - frames % 17) % 17
    width, height = (480, 864) if str(body.get("orientation") or "portrait") == "portrait" else (864, 480)
    prefix = f"short_drama/h3_rv2v_{_safe_name(job_id)}_{uuid4().hex[:8]}"
    prompt = str(optimized_prompt or "").strip()
    if not prompt:
        raise RuntimeError("H3 Ref2VA禁止使用未优化的原始提示词")
    graph = {
        "1":{"class_type":"UNETLoader","inputs":{"unet_name":H3_REF2VA_MODEL,"weight_dtype":"default"}},
        "2":{"class_type":"CLIPLoader","inputs":{"clip_name":H3_TEXT_ENCODER,"type":"minimax","device":"default"}},
        "3":{"class_type":"VAELoader","inputs":{"vae_name":H3_VIDEO_VAE}},
        "4":{"class_type":"VAELoader","inputs":{"vae_name":H3_AUDIO_VAE}},
        "5":{"class_type":"LoadImage","inputs":{"image":identity_name}},
        "6":{"class_type":"VHS_LoadVideoPath","inputs":{"video":str(source_video),"force_rate":24,"custom_width":width,"custom_height":height,"frame_load_cap":frames,"skip_first_frames":0,"select_every_nth":1,"format":"None"}},
        "7":{"class_type":"MiniMaxH3ReferenceToVideo","inputs":{"clip":["2",0],"vae":["3",0],"audio_vae":["4",0],"prompt":prompt,"width":width,"height":height,"length":frames,"ref_image_size":"max","ref_images":{"ref_image_0":["5",0]},"ref_videos":{"ref_video_0":["6",0]}}},
        "8":{"class_type":"RandomNoise","inputs":{"noise_seed":int(time.time_ns() % (2**63))}},
        "9":{"class_type":"KSamplerSelect","inputs":{"sampler_name":"res_multistep"}},
        "10":{"class_type":"BasicScheduler","inputs":{"model":["1",0],"scheduler":"normal","steps":20,"denoise":1.0}},
        "11":{"class_type":"BasicGuider","inputs":{"model":["1",0],"conditioning":["7",0]}},
        "12":{"class_type":"SamplerCustomAdvanced","inputs":{"noise":["8",0],"guider":["11",0],"sampler":["9",0],"sigmas":["10",0],"latent_image":["7",1]}},
        "13":{"class_type":"VAEDecode","inputs":{"samples":["12",0],"vae":["3",0]}},
        "15":{"class_type":"CreateVideo","inputs":{"images":["13",0],"fps":24,"bit_depth":8}},
        "16":{"class_type":"SaveVideo","inputs":{"video":["15",0],"filename_prefix":prefix,"format":"mp4","codec":"auto"}},
    }
    prompt_id = ""
    try:
        prompt_id = str(_comfy_json("/prompt", {"prompt":graph}, timeout=30)["prompt_id"])
        _update_video_job(job_id, status="generating", stage="h3_rv2v", model="MiniMax H3 Ref2VA INT8", comfy_prompt_id=prompt_id,
                          heartbeat_at=_iso_now(), source_video_url=str(body.get("source_video_url") or ""),
                          identity_reference_url=str(body.get("identity_reference_url") or ""))
        deadline = time.time() + VIDEO_TASK_TIMEOUT_SECONDS
        while time.time() < deadline:
            current = _load_video_jobs().get("jobs", {}).get(job_id, {})
            if _video_job_stopping(current):
                raise RuntimeError(str(current.get("error") or "视频任务已停止"))
            record = _comfy_json(f"/history/{prompt_id}", timeout=30).get(prompt_id)
            if record:
                status = record.get("status", {})
                if status.get("status_str") == "error":
                    raise RuntimeError("MiniMax H3 Ref2VA执行失败")
                if status.get("status_str") == "success":
                    matches = sorted(COMFY_OUTPUT.glob(f"{prefix}*.mp4"), key=lambda path:path.stat().st_mtime, reverse=True)
                    if not matches:
                        raise RuntimeError("MiniMax H3未生成视频文件")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(matches[0], target)
                    return target
            _update_video_job(job_id, heartbeat_at=_iso_now(), stage="h3_rv2v")
            time.sleep(2)
        raise TimeoutError("MiniMax H3 Ref2VA超过硬截止时间")
    finally:
        if prompt_id:
            _wait_for_video_comfy_prompts(job_id, [prompt_id])
        identity_input.unlink(missing_ok=True)
        _free_comfy_memory()


def _run_h3_context_then_ref2va(job_id: str, body: dict, target: Path, *, duration: int, instruction: str) -> str:
    context_prompt = (
        "Use <Video 1> as the exact geometry, blocking, camera motion and occlusion reference. "
        "Use <Picture 1> as the exact protagonist facial identity reference. Preserve the same face, hair, costume, body proportions, "
        "environment layout and lighting across every frame. Replace only the synthetic 3D facial appearance with the 2D identity; "
        "do not change camera timing or scene geometry. No text, watermark, duplicate person, face drift, body deformation or flicker. "
        f"Shot direction: {instruction}"
    )
    optimized_prompt = _optimize_h3_ref2va_prompt(job_id, body, duration=duration, prompt=context_prompt)
    current = _load_video_jobs().get("jobs", {}).get(job_id, {})
    if _video_job_stopping(current):
        raise RuntimeError(str(current.get("error") or "视频任务已停止"))
    if _ollama_model_loaded(H3_CONTEXT_IR_MODEL):
        raise RuntimeError("H3 Context IR模型仍驻留，禁止启动H3 Ref2VA")
    _require_memory(55 * GIB)
    _invoke_production_capability(
        "video.shot.h3_ref2va", job_id=job_id, body=body, target=target,
        duration=duration, optimized_prompt=optimized_prompt,
    )
    return optimized_prompt


def _generate_video_job(job_id: str, body: dict) -> None:
    subject_key = _video_key(body)
    process: subprocess.Popen[str] | None = None
    try:
        with _claim_production_resource("video", job_id, estimated_memory=VIDEO_ESTIMATED_MEMORY, timeout=VIDEO_QUEUE_TIMEOUT_SECONDS, identity=body):
            current = _load_video_jobs().get("jobs", {}).get(job_id, {})
            if current.get("status") == "cancelled": return
            _require_memory(VIDEO_ESTIMATED_MEMORY)
            image = _local_media_path(body.get("image_url"))
            episode = max(1, int(body.get("episode", 1))); shot = max(1, int(body.get("shot_number", 1)))
            use_h3_rv2v = bool(body.get("source_video_url") and body.get("identity_reference_url"))
            duration_limit = 15 if use_h3_rv2v else 5
            duration = min(duration_limit, max(1, int(round(float(body.get("business_duration", 2))))))
            target_dir = OUTPUT_ROOT / "videos"; target_dir.mkdir(parents=True, exist_ok=True)
            target = target_dir / f"episode_{episode}_shot_{shot}.mp4"
            motion = body.get("motion_strategy") if isinstance(body.get("motion_strategy"), dict) else {}
            instruction = str(motion.get("instruction") or body.get("prompt") or "").strip()
            camera_ratio = max(0.0, min(1.0, float(motion.get("camera_movement_ratio", 0.35))))
            action_ratio = max(0.0, min(1.0, float(motion.get("subject_action_ratio", 0.65))))
            positive = (
                "cinematic realistic live-action shot, preserve the exact identity, face geometry, hairstyle, costume, body proportions, "
                "scene layout, walls, doors, windows, furniture positions and lighting from the input image across every frame, "
                "stable facial features, stable background geometry, temporally coherent details, subtle natural movement, "
                f"camera motion intensity {camera_ratio:.2f}, subject action intensity {action_ratio:.2f}. {instruction}. "
                f"Mandatory production rules: {_production_spec_for('video')}"
            )
            negative = (
                "identity change, face morphing, deformed face, asymmetrical eyes, warped mouth, melted skin, malformed hands, extra fingers, "
                "warped body, changing clothes, duplicate person, background morphing, moving walls, bent doors, distorted furniture, "
                "flicker, temporal inconsistency, blur, camera shake, abrupt zoom, fast pan, text, watermark"
            )
            if use_h3_rv2v:
                optimized_prompt = _run_h3_context_then_ref2va(job_id, body, target, duration=duration, instruction=instruction)
                _commit_video_terminal(job_id, status="completed", stage="completed", engine="minimax-h3-ref2va",
                                  optimized_prompt=optimized_prompt,
                                  audio_mode="not_applicable_h3_source_video",
                                  video={"url":f"/api/result-media?filename={target.name}&subfolder=videos"},
                                  finished_at=_iso_now(), heartbeat_at=_iso_now(), pid=None, process_group=None)
                return
            subprocess.run(["/Users/aoo/AI/Tools/ComfyUI/main/ComfyUI/.venv/bin/python3", "/Users/aoo/AI/Projects/ShortDramaPipeline/bin/start_comfy.py"], check=True, capture_output=True, text=True, timeout=120)
            script = """from pathlib import Path
import shutil,sys
sys.path.insert(0,'/Users/aoo/AI/Projects/ShortDramaPipeline/pipeline')
import comfy_client
source=Path(sys.argv[1]); target=Path(sys.argv[2]); frames=int(sys.argv[3])
result=comfy_client.wan22_img2vid(source,sys.argv[6],sys.argv[7],f'short_drama/episode_{sys.argv[4]}_shot_{sys.argv[5]}',frames=frames,fps=16,width=576,height=1024,steps=20)
shutil.copy2(result,target)
"""
            command = ["/Users/aoo/AI/Tools/ComfyUI/main/ComfyUI/.venv/bin/python3", "-c", script, str(image), str(target), str(duration * 16 + 1), str(episode), str(shot), positive, negative]
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
            with VIDEO_JOB_LOCK:
                ACTIVE_VIDEO_PROCESSES[job_id] = process
            _update_video_job(job_id, status="generating", stage="model_inference", pid=process.pid, process_group=os.getpgid(process.pid), heartbeat_at=_iso_now())
            started = time.time()
            while process.poll() is None:
                current = _load_video_jobs().get("jobs", {}).get(job_id, {})
                if _video_job_stopping(current):
                    _terminate_process_tree(process); raise RuntimeError(str(current.get("error") or "视频任务已停止"))
                if time.time() - started > VIDEO_TASK_TIMEOUT_SECONDS:
                    _terminate_process_tree(process); raise TimeoutError("视频生成超过硬截止时间")
                _update_video_job(job_id, heartbeat_at=_iso_now(), stage="model_inference")
                time.sleep(1)
            stdout, stderr = process.communicate()
            if process.returncode:
                raise RuntimeError((stderr or stdout or "视频模型进程失败")[-500:])
            if not target.is_file(): raise RuntimeError("视频模型未生成输出文件")
            _commit_video_terminal(job_id, status="completed", stage="completed", video={"url":f"/api/result-media?filename={target.name}&subfolder=videos"}, finished_at=_iso_now(), heartbeat_at=_iso_now(), pid=None, process_group=None)
    except Exception as error:
        if process and process.poll() is None: _terminate_process_tree(process)
        current = _load_video_jobs().get("jobs", {}).get(job_id, {})
        prompt_ids = [str(current.get(key) or "").strip() for key in ("context_ir_prompt_id", "comfy_prompt_id")]
        _wait_for_video_comfy_prompts(job_id, prompt_ids)
        if current.get("cancel_requested_at") or current.get("status") == "cancelled":
            RESOURCE_SCHEDULER.cancel_job(job_id)
            _commit_video_terminal(job_id, status="cancelled", stage="cancelled", error="视频任务已停止", finished_at=_iso_now(), heartbeat_at=_iso_now(), pid=None, process_group=None)
        else:
            engine = "MiniMax H3 Ref2VA" if body.get("source_video_url") and body.get("identity_reference_url") else "Wan2.2"
            _commit_video_terminal(job_id, status="failed", stage="failed", error=f"{engine} 分镜视频生成失败：{str(error)[:500]}", finished_at=_iso_now(), heartbeat_at=_iso_now(), pid=None, process_group=None)
    finally:
        with VIDEO_JOB_LOCK:
            ACTIVE_VIDEO_PROCESSES.pop(job_id, None); ACTIVE_VIDEO_JOBS.discard(job_id)
            if ACTIVE_VIDEO_SUBJECTS.get(subject_key) == job_id: ACTIVE_VIDEO_SUBJECTS.pop(subject_key, None)
        _free_comfy_memory()


def _launch_waiting_video_job(job_id: str, body: dict) -> None:
    with VIDEO_JOB_LOCK:
        if job_id in ACTIVE_VIDEO_JOBS:
            return
        jobs = _load_video_jobs()
        current = jobs.setdefault("jobs", {}).get(job_id, {})
        if current.get("status") != "waiting_memory":
            return
        current.update({"status":"generating", "stage":"starting", "started_at":_iso_now(), "heartbeat_at":_iso_now()})
        jobs["jobs"][job_id] = current
        _save_video_jobs(jobs)
        ACTIVE_VIDEO_JOBS.add(job_id); ACTIVE_VIDEO_SUBJECTS[str(current.get("subject_key"))] = job_id
    threading.Thread(target=_invoke_production_capability, args=("video.shot",), kwargs={"job_id":job_id, "body":body}, daemon=True, name=f"video-{job_id[:8]}").start()


def _recover_terminal_video_prompt(job_id: str, body: dict, terminal_status: str, terminal_stage: str, terminal_error: str) -> None:
    subject_key = _video_key(body)
    try:
        with _claim_production_resource("video", job_id, estimated_memory=0, timeout=VIDEO_QUEUE_TIMEOUT_SECONDS, identity=body):
            current = _load_video_jobs().get("jobs", {}).get(job_id, {})
            prompt_ids = [str(current.get(key) or "").strip() for key in ("context_ir_prompt_id", "comfy_prompt_id")]
            _wait_for_video_comfy_prompts(job_id, prompt_ids)
            _update_video_job(job_id, status=terminal_status, stage=terminal_stage, error=terminal_error,
                              prompt_recovered_at=_iso_now(), finished_at=current.get("finished_at") or _iso_now(), heartbeat_at=_iso_now())
    finally:
        with VIDEO_JOB_LOCK:
            ACTIVE_VIDEO_JOBS.discard(job_id)
            if ACTIVE_VIDEO_SUBJECTS.get(subject_key) == job_id:
                ACTIVE_VIDEO_SUBJECTS.pop(subject_key, None)


def _monitor_waiting_video_jobs() -> None:
    while not VIDEO_MEMORY_MONITOR_STOP.wait(VIDEO_WATCHDOG_SECONDS):
        now = time.time()
        recoveries: list[tuple[str, dict, str, str, str]] = []
        with VIDEO_JOB_LOCK:
            jobs = _load_video_jobs(); changed = False
            for job_id, job in jobs.get("jobs", {}).items():
                process = ACTIVE_VIDEO_PROCESSES.get(job_id); running = bool(process and process.poll() is None)
                status = str(job.get("status")); age = now - _parse_job_time(job.get("heartbeat_at") or job.get("queued_at"))
                if status in {"completed", "failed", "cancelled"}:
                    prompt_ids = [str(job.get(key) or "").strip() for key in ("context_ir_prompt_id", "comfy_prompt_id")]
                    queued = False
                    for prompt_id in dict.fromkeys(value for value in prompt_ids if value):
                        try:
                            queued = queued or _comfy_prompt_queue_state(prompt_id) != "absent"
                        except Exception:
                            queued = True
                    if queued and not _cancel_job_comfy_prompts(job, confirm_seconds=2.0):
                        terminal_stage, terminal_error = str(job.get("stage") or status), str(job.get("error") or "")
                        job.update({"status":"generating", "stage":"cancel_pending", "pending_terminal_status":status,
                                    "pending_terminal_stage":terminal_stage, "pending_terminal_error":terminal_error,
                                    "heartbeat_at":_iso_now(), "error":"看门狗发现终态任务仍有所属Comfy prompt，正在恢复核销"})
                        request_body = dict(job.get("request") or {})
                        ACTIVE_VIDEO_JOBS.add(job_id); ACTIVE_VIDEO_SUBJECTS[str(job.get("subject_key") or _video_key(request_body))] = job_id
                        recoveries.append((job_id, request_body, status, terminal_stage, terminal_error)); changed = True
                elif status == "generating" and not running and job_id in ACTIVE_VIDEO_PROMPT_CANCELLERS:
                    continue
                elif status == "generating" and str(job.get("stage")) == "cancel_pending" and job_id not in ACTIVE_VIDEO_JOBS:
                    request_body = dict(job.get("request") or {})
                    terminal_status = str(job.get("pending_terminal_status") or ("cancelled" if job.get("cancel_requested_at") else "failed"))
                    terminal_stage = str(job.get("pending_terminal_stage") or terminal_status)
                    terminal_error = str(job.get("pending_terminal_error") or job.get("error") or "残留Comfy prompt已回收")
                    ACTIVE_VIDEO_JOBS.add(job_id); ACTIVE_VIDEO_SUBJECTS[str(job.get("subject_key") or _video_key(request_body))] = job_id
                    recoveries.append((job_id, request_body, terminal_status, terminal_stage, terminal_error))
                elif status == "generating" and not running and age > VIDEO_WATCHDOG_SECONDS * 3:
                    if _cancel_job_comfy_prompts(job):
                        job.update({"status":"failed", "stage":"failed", "error":"看门狗已回收无实际进程的视频任务", "finished_at":_iso_now(), "pid":None, "process_group":None}); changed = True
                        ACTIVE_VIDEO_JOBS.discard(job_id)
                    else:
                        job.update({"status":"generating", "stage":"cancel_pending", "error":"看门狗等待所属Comfy prompt退出", "heartbeat_at":_iso_now()}); changed = True
                elif status == "waiting_memory" and age > VIDEO_QUEUE_TIMEOUT_SECONDS:
                    job.update({"status":"failed", "stage":"failed", "error":"视频任务排队超时", "finished_at":_iso_now()}); changed = True
                elif running and status not in {"generating"}:
                    if _cancel_job_comfy_prompts(job):
                        _terminate_process_tree(process); ACTIVE_VIDEO_PROCESSES.pop(job_id, None); ACTIVE_VIDEO_JOBS.discard(job_id); changed = True
            if changed: _save_video_jobs(jobs)
            waiting = None if ACTIVE_VIDEO_JOBS or _heavy_task_busy() else next(((job_id, job) for job_id, job in jobs.get("jobs", {}).items() if job.get("status") == "waiting_memory" and isinstance(job.get("request"), dict)), None)
        for recovery in recoveries:
            threading.Thread(target=_recover_terminal_video_prompt, args=recovery, daemon=True, name=f"video-prompt-recovery-{recovery[0][:8]}").start()
        if not waiting: continue
        job_id, job = waiting
        ready, memory = _memory_ready(VIDEO_ESTIMATED_MEMORY)
        _update_video_job(job_id, memory=memory, heartbeat_at=_iso_now())
        if ready: _launch_waiting_video_job(job_id, job["request"])


def _recover_video_jobs() -> None:
    recoveries: list[tuple[str, dict, str, str, str]] = []
    with VIDEO_JOB_LOCK:
        ACTIVE_VIDEO_JOBS.clear(); ACTIVE_VIDEO_SUBJECTS.clear(); ACTIVE_VIDEO_PROCESSES.clear()
        store = _load_video_jobs(); changed = False
        for job_id, job in store.get("jobs", {}).items():
            if job.get("status") in {"generating", "waiting_memory"}:
                if _cancel_job_comfy_prompts(job):
                    job.update({"status":"failed", "stage":"failed", "error":"服务重启已回收视频任务，请重新生成", "finished_at":_iso_now(), "pid":None, "process_group":None}); changed = True
                else:
                    request_body = dict(job.get("request") or {})
                    job.update({"status":"generating", "stage":"cancel_pending", "error":"服务重启正在核销残留Comfy prompt", "heartbeat_at":_iso_now()}); changed = True
                    ACTIVE_VIDEO_JOBS.add(job_id); ACTIVE_VIDEO_SUBJECTS[str(job.get("subject_key") or _video_key(request_body))] = job_id
                    recoveries.append((job_id, request_body, "failed", "failed", "服务重启已回收视频任务，请重新生成"))
        if changed: _save_video_jobs(store)
    for recovery in recoveries:
        threading.Thread(target=_recover_terminal_video_prompt, args=recovery, daemon=True, name=f"video-restart-recovery-{recovery[0][:8]}").start()


def _shutdown_video_jobs() -> None:
    with VIDEO_JOB_LOCK:
        running = list(ACTIVE_VIDEO_PROCESSES.values())
    for process in running: _terminate_process_tree(process)
    with VIDEO_JOB_LOCK:
        store = _load_video_jobs(); changed = False
        for job in store.get("jobs", {}).values():
            if job.get("status") in {"generating", "waiting_memory"}:
                if _cancel_job_comfy_prompts(job):
                    job.update({"status":"failed", "stage":"failed", "error":"服务关闭已回收视频任务", "finished_at":_iso_now(), "pid":None, "process_group":None}); changed = True
                else:
                    job.update({"status":"generating", "stage":"cancel_pending", "error":"服务关闭时所属Comfy prompt尚未退出，等待重启恢复核销", "heartbeat_at":_iso_now()}); changed = True
        if changed: _save_video_jobs(store)
        ACTIVE_VIDEO_PROCESSES.clear()


def _load_resources() -> dict:
    if not RESOURCES_FILE.exists(): return {"resources": []}
    try: return json.loads(RESOURCES_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError): return {"resources": []}


def _save_resources(store: dict) -> None:
    atomic_write_json(RESOURCES_FILE, store, prefix="resources-")


def _project_generation_context(body: dict) -> str:
    project_id = str(body.get("project_id", "")).strip()
    project = next((item for item in _load_store().get("projects", []) if str(item.get("id", "")) == project_id), {})
    return "\n".join(str(project.get(key, "")) for key in ("category", "topic", "style"))


def _load_lora_indexes() -> tuple[dict, dict]:
    """Load both authoritative LoRA indexes for every image request."""
    try:
        primary = json.loads(LORA_INDEX_FILE.read_text(encoding="utf-8"))
        commercial = json.loads(COMMERCIAL_LORA_INDEX_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError("LoRA 索引缺失或损坏") from error
    if not isinstance(primary.get("styles"), list) or not isinstance(commercial.get("models"), list):
        raise RuntimeError("LoRA 索引结构无效")
    return primary, commercial


def _scan_lora_style_directories() -> list[dict]:
    """Return live top-level LoRA styles directly from the local model tree."""
    if not LORA_ROOT.is_dir():
        return []
    styles = []
    for directory in LORA_ROOT.iterdir():
        if not directory.is_dir() or directory.name.startswith("."):
            continue
        weights = sorted(path for path in directory.rglob("*.safetensors") if path.is_file())
        # A visual style is also a project/prompt contract. Keep an explicitly
        # documented style selectable while its optional LoRA inventory is
        # empty; unrelated empty placeholder directories remain hidden.
        readme = directory / "README.md"
        if not weights and not readme.is_file():
            continue
        timestamps = [path.stat().st_mtime_ns for path in weights]
        if readme.is_file():
            timestamps.append(readme.stat().st_mtime_ns)
        styles.append({
            "id": directory.name,
            "name": directory.name,
            "model_count": len(weights),
            "updated_at": max(timestamps),
        })
    return sorted(styles, key=lambda item: item["name"])


def _validate_project_visual_style(body: dict, available_style_ids: set[str] | None = None) -> str:
    category = str(body.get("category", "")).strip()
    style = str(body.get("style", "")).strip()
    available = available_style_ids if available_style_ids is not None else {
        str(item.get("id", "")) for item in _scan_lora_style_directories()
    }
    if not category or category != style or category not in available:
        raise ValueError("invalid_visual_style")
    return category


def _indexed_flux_lora(display_name: str, *, lora_id: str, era: str, scale: float) -> dict:
    primary, _ = _load_lora_indexes()
    record = next((item for item in primary["styles"] if item.get("display_name") == display_name), None)
    if not record:
        raise RuntimeError(f"LoRA 索引未登记：{display_name}")
    path = (LORA_ROOT / str(record.get("file", ""))).resolve()
    if LORA_ROOT.resolve() not in path.parents or not path.is_file():
        raise RuntimeError(f"LoRA 索引文件不存在：{display_name}")
    expected = str(record.get("sha256", "")).strip().lower()
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if not expected or actual != expected:
        raise RuntimeError(f"LoRA 索引校验失败：{display_name}")
    base_model = str(primary.get("base_model", ""))
    if base_model != "black-forest-labs/FLUX.1-dev":
        raise RuntimeError(f"LoRA 底模不兼容：{display_name}")
    triggers = [str(item).strip() for item in record.get("trigger_words", []) if str(item).strip()]
    if not triggers:
        raise RuntimeError(f"LoRA 触发词缺失：{display_name}")
    return {
        "id": lora_id,
        "era": era,
        "style": display_name,
        "path": path,
        "scale": scale,
        "triggers": triggers,
        "index": str(LORA_INDEX_FILE),
        "sha256": actual,
        "base_model": base_model,
    }


def _verified_commercial_lora(record: dict) -> dict:
    path = Path(str(record.get("path", ""))).resolve()
    if LORA_ROOT not in path.parents or not path.is_file():
        raise RuntimeError("人物 LoRA 文件不存在")
    expected = str(record.get("sha256", "")).strip().lower()
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if not expected or actual != expected:
        raise RuntimeError("人物 LoRA 索引校验失败")
    if not bool(record.get("commercial_use")):
        raise RuntimeError("人物 LoRA 未获商用许可")
    base_model = str(record.get("base_model", ""))
    if base_model != "stabilityai/stable-diffusion-xl-base-1.0":
        raise RuntimeError("人物 LoRA 底模不兼容")
    return {
        "id": str(record.get("filename", "")),
        "path": str(path),
        "comfy_name": str(path.relative_to(LORA_ROOT)),
        "sha256": actual,
        "base_model": base_model,
        "scale": 0.65,
    }


def _character_lora_assignment(body: dict) -> dict | None:
    if str(body.get("asset_kind", "")) != "character":
        return None
    _, commercial = _load_lora_indexes()
    project_id = str(body.get("project_id", "")).strip()
    subject = str(body.get("asset_subject", "")).split(":", 1)[0].strip()
    project = next((item for item in _load_store().get("projects", []) if str(item.get("id", "")) == project_id), None)
    if not project or not subject:
        raise RuntimeError("人物 LoRA 缺少项目或人物标识")
    characters = project.get("stage_state", {}).get("assets", {}).get("data", {}).get("characters", [])
    current = next((item for item in characters if str(item.get("name", "")) == subject), {})
    requested = str(body.get("character_lora_id", "") or current.get("character_lora_id", "")).strip()
    used = {
        str(item.get("character_lora_id", ""))
        for item in characters
        if str(item.get("name", "")) != subject and str(item.get("character_lora_id", ""))
    }
    style = str(project.get("style", "") or project.get("category", "")).strip()
    gender = str(body.get("character_gender", "") or current.get("gender", "")).strip()
    gender_prefix = "女性_" if any(token in gender for token in ("女", "female")) else "男性_"
    candidates = sorted(
        (item for item in commercial["models"] if str(item.get("category", "")) == f"{style}/人物LoRA" and str(item.get("filename", "")).startswith(gender_prefix)),
        key=lambda item: str(item.get("filename", "")),
    )
    if requested:
        record = next((item for item in candidates if str(item.get("filename", "")) == requested), None)
        if not record:
            raise RuntimeError(f"人物 LoRA 不属于当前风格或性别：{subject}")
        if requested in used:
            raise RuntimeError(f"人物 LoRA 在当前项目内重复占用：{requested}")
        return _verified_commercial_lora(record)
    preferred_traits = ("亚洲面孔", "清透肖像", "真人插画", "极致细节", "微观", "电影光影", "电影柔光", "自然手部", "动态骨骼", "柔和大光")
    def candidate_rank(item: dict) -> tuple[int, str]:
        filename = str(item.get("filename", ""))
        return (next((index for index, trait in enumerate(preferred_traits) if trait in filename), len(preferred_traits)), filename)
    ordered = sorted(candidates, key=candidate_rank)
    same_gender_names = [
        str(item.get("name", "")) for item in characters
        if ("女性_" if any(token in str(item.get("gender", "")) for token in ("女", "female")) else "男性_") == gender_prefix
    ]
    preferred_index = same_gender_names.index(subject) if subject in same_gender_names else 0
    ordered = ordered[preferred_index:] + ordered[:preferred_index]
    available = [item for item in ordered if str(item.get("filename", "")) not in used]
    if not available:
        raise RuntimeError(f"当前项目没有可用的唯一人物 LoRA：{subject}")
    return _verified_commercial_lora(available[0])


def _project_style_lora(body: dict) -> dict:
    _, commercial = _load_lora_indexes()
    project_id = str(body.get("project_id", "")).strip()
    project = next((item for item in _load_store().get("projects", []) if str(item.get("id", "")) == project_id), None)
    if not project:
        raise RuntimeError("风格 LoRA 缺少项目标识")
    style = str(project.get("style", "") or project.get("category", "")).strip()
    candidates = sorted(
        (item for item in commercial["models"] if str(item.get("category", "")) == f"{style}/风格LoRA"),
        key=lambda item: str(item.get("filename", "")),
    )
    if not candidates:
        raise RuntimeError(f"当前项目风格没有可用 LoRA：{style}")
    offset = int(hashlib.sha256(project_id.encode()).hexdigest()[:8], 16) % len(candidates)
    return _verified_commercial_lora(candidates[offset])



def _automatic_lora(body: dict, prompt: str) -> dict | None:
    _load_lora_indexes()
    specific = prompt.lower()
    fallback = _project_generation_context(body).lower()
    ancient_tokens = ("古代", "汉服", "襦裙", "唐装", "宋制", "明制", "清装", "宫廷", "江湖", "武侠", "仙侠")
    modern_tokens = ("现代", "当代", "都市", "西装", "衬衫", "领带", "职场", "商务", "手机", "电脑", "汽车")
    project_ancient = any(token in fallback for token in ancient_tokens + ("古风", "神话", "宗门", "修仙"))
    project_modern = any(token in fallback for token in modern_tokens)
    specific_ancient = any(token in specific for token in ancient_tokens + ("古风", "宗门", "修仙"))
    specific_modern = any(token in specific for token in modern_tokens)
    # The project-wide era/style is authoritative; accidental per-character wording must never switch LoRA families.
    ancient = project_ancient if project_ancient != project_modern else specific_ancient and not specific_modern
    specific_anime = any(token in specific for token in ("二次元", "动漫", "动画", "漫画", "anime"))
    specific_illustration = any(token in specific for token in ("插画", "绘本", "平涂", "厚涂", "illustration"))
    specific_realistic = any(token in specific for token in ("真人", "写实", "电影", "摄影", "真实肌理", "院线"))
    has_specific_style = specific_anime or specific_illustration or specific_realistic
    anime = specific_anime if has_specific_style else any(token in fallback for token in ("二次元", "动漫", "anime"))
    illustration = specific_illustration if has_specific_style else any(token in fallback for token in ("插画", "绘本", "illustration"))
    realistic = specific_realistic if has_specific_style else any(token in fallback for token in ("真人", "写实", "电影", "摄影", "院线"))
    mode = str(body.get("lora_mode", "automatic") or "automatic")
    requested = str(body.get("lora_id", "") or "")
    if mode in {"fixed", "manual"}:
        if requested == "cn-mythic": ancient = True
        elif requested in {"cn-romance", "cn-suspense"}: illustration = True
        elif requested == "cn-modern": realistic = True; illustration = False
    def available(display_name: str, *, lora_id: str, era: str, scale: float) -> dict | None:
        try:
            return _indexed_flux_lora(display_name, lora_id=lora_id, era=era, scale=scale)
        except RuntimeError as error:
            if "LoRA 索引未登记" in str(error) or "LoRA 索引文件不存在" in str(error):
                return None
            raise
    if anime:
        return available("二次元", lora_id="anime", era="二次元", scale=0.85)
    if ancient and realistic:
        return available("古风写实", lora_id="ancient-realistic", era="古代", scale=0.78)
    if ancient:
        return available("古风", lora_id="ancient", era="古代", scale=0.75)
    if illustration:
        return available("现代", lora_id="modern-illustration", era="现代", scale=0.72)
    if realistic and str(body.get("asset_kind", "")) == "character":
        return available("现代写实", lora_id="modern-realistic-portrait", era="现代", scale=0.75)
    return None


def _generate_image(
    name: object,
    prompt: object,
    width: object,
    height: object,
    lora: dict | None = None,
    *,
    job_id: str | None = None,
    guidance: float | None = None,
    steps: int | None = None,
    model: str | None = None,
    base_model: str | None = None,
    quantize: int | None = None,
) -> dict:
    generator = FLUX_LORA_GENERATOR if lora else MFLUX_FLUX2
    if not generator.is_file():
        raise RuntimeError("MLX 生图执行器未安装")
    image_dir = OUTPUT_ROOT / "images"
    image_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{_safe_name(name)}.png"
    target = image_dir / filename
    with _claim_production_resource("image", job_id or f"image-{_safe_name(name)}", timeout=1800):
        pixel_count = max(256, min(1664, int(width or 928))) * max(256, min(1664, int(height or 1664)))
        is_klein9b = (base_model or "") == "flux2-klein-9b"
        estimated_memory = max(42 * GIB if is_klein9b else 40 * GIB if lora else 0, int((16 + 8 * pixel_count / 1_000_000) * GIB))
        _wait_for_post_comfy_memory(estimated_memory, job_id=job_id)
        if not target.is_file():
            if lora:
                lora_path = Path(lora["path"])
                if not lora_path.is_file(): raise RuntimeError(f"自动匹配的 LoRA 不存在：{lora_path.name}")
                enriched_prompt = f"{', '.join(lora['triggers'])}, {prompt or 'cinematic vertical film still'}"
                command = [str(COMFY_PYTHON), str(generator), "--model", "ModelsLab/flux.1-dev", "--steps", "8", "--guidance", "3.5",
                           "--max-sequence-length", "256", "--lora", str(lora_path), "--scale", str(lora["scale"]),
                           "--width", str(max(256, min(1664, int(width or 928)))), "--height", str(max(256, min(1664, int(height or 1664)))),
                           "--prompt", enriched_prompt, "--output", str(target)]
            else:
                effective_steps = max(1, min(50, int(steps if steps is not None else 4)))
                command = [str(generator), "--model", str(model or "flux2-klein-4b")]
                if base_model:
                    command.extend(["--base-model", base_model])
                command.extend(["--quantize", str(int(quantize if quantize is not None else 4)), "--steps", str(effective_steps)])
                if guidance is not None:
                    command.extend(["--guidance", str(float(guidance))])
                command.extend([
                    "--width", str(max(256, min(1664, int(width or 928)))), "--height", str(max(256, min(1664, int(height or 1664)))),
                    "--prompt", str(prompt or "cinematic vertical film still"), "--output", str(target),
                ])
            _run_image_process(job_id or str(name), command, cwd=APPLICATION_ROOT, target=target)
    return {"url": f"/api/result-media?filename={filename}&subfolder=images", "filename": filename, "subfolder": "images", "steps":int(steps if steps is not None else (8 if lora else 4)), "cfg":float(guidance if guidance is not None else 3.5), "quantization":("" if lora else f"{int(quantize if quantize is not None else 4)}-bit"), "lora":({"id":lora["id"], "era":lora["era"], "style":lora["style"], "scale":lora["scale"], "index":lora["index"], "sha256":lora["sha256"], "base_model":lora["base_model"]} if lora else {"id":"none", "era":"现代", "style":"写实基础模型", "scale":0, "index":str(LORA_INDEX_FILE), "base_model":str(base_model or model or "flux2-klein-4b")})}


def _klein9b_houtu_loras(body: dict) -> list[dict]:
    project_id = str(body.get("project_id") or "")
    project = next((item for item in _load_store().get("projects", []) if str(item.get("id", "")) == project_id), {})
    project_style = str(project.get("style") or project.get("category") or body.get("style") or "").strip()
    if project_style != "国风厚涂":
        return []
    try:
        catalog = json.loads(KLEIN9B_TEST_LORA_INDEX_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError("FLUX.2 Klein 9B国风厚涂LoRA索引缺失或损坏") from error
    if catalog.get("production_enabled") is not True:
        raise RuntimeError("FLUX.2 Klein 9B国风厚涂LoRA尚未启用")
    records = catalog.get("models")
    if not isinstance(records, list):
        raise RuntimeError("FLUX.2 Klein 9B国风厚涂LoRA索引结构无效")

    def checked(prefix: str, category: str, scale: float, *, required: bool = False) -> dict | None:
        item = next((entry for entry in records if str(entry.get("category")) == category and str(entry.get("filename", "")).startswith(prefix)), None)
        if item is None:
            if required:
                raise RuntimeError(f"FLUX.2 Klein 9B LoRA索引缺少批准项：{category}/{prefix}")
            return None
        if item.get("production_approved") is not True:
            return None
        path = (APPLICATION_ROOT / str(item.get("path", ""))).resolve()
        if not path.is_file() or path.stat().st_size != int(item.get("size") or 0):
            raise RuntimeError(f"FLUX.2 Klein 9B LoRA文件缺失：{path.name}")
        if hashlib.sha256(path.read_bytes()).hexdigest() != str(item.get("sha256") or ""):
            raise RuntimeError(f"FLUX.2 Klein 9B LoRA校验失败：{path.name}")
        return {"path":path, "scale":scale, "trigger":str(item.get("trigger") or "").strip(), "sha256":item["sha256"], "filename":path.name}

    selected = [checked("风格_古代幻想厚涂_", "风格LoRA", 0.9, required=True)]
    kind = str(body.get("asset_kind") or "").strip()
    if kind == "character":
        gender = str(body.get("character_gender") or "").lower()
        prompt_text = str(body.get("prompt") or "").lower()
        female = any(token in gender for token in ("女", "female", "woman", "girl")) or (
            not gender and any(token in prompt_text for token in ("女性", "少女", "女孩", "女主", "female", "woman", "girl"))
        )
        selected.append(checked("女性_" if female else "男性_", "人物LoRA", 0.72))
    elif kind in {"animal", "spirit_beast"}:
        selected.append(checked("灵兽_", "灵兽LoRA", 0.75))
    return [item for item in selected if item is not None]


def _uses_klein9b_houtu(body: dict) -> bool:
    project_id = str(body.get("project_id") or "")
    project = next((item for item in _load_store().get("projects", []) if str(item.get("id", "")) == project_id), {})
    return str(project.get("style") or project.get("category") or body.get("style") or "").strip() == "国风厚涂"


def _generate_klein9b_asset_baseline(name: object, prompt: str, width: object, height: object, *, job_id: str, body: dict | None = None) -> dict:
    request_body = body or {}
    target = OUTPUT_ROOT / "images" / f"{_safe_name(name)}.png"
    target.parent.mkdir(parents=True, exist_ok=True)
    width_value = max(512, min(1024, int(width or 928))) // 16 * 16
    height_value = max(768, min(1664, int(height or 1664))) // 16 * 16
    _update_image_job(job_id, status="processing", phase="klein9b_baseline", model="FLUX.2 Klein 9B 8-bit", heartbeat_at=_iso_now())
    _wait_for_post_comfy_memory(42 * GIB, job_id=job_id)
    loras = _klein9b_houtu_loras(request_body)
    triggers = [item["trigger"] for item in loras if item["trigger"]]
    effective_prompt = f"{', '.join(triggers)}, {prompt}" if triggers else prompt
    command = [str(MFLUX_FLUX2), "--model", ASSET_3D_KLEIN9B_MODEL, "--base-model", "flux2-klein-9b", "--steps", "8",
               "--width", str(width_value), "--height", str(height_value), "--prompt", effective_prompt[:3000], "--output", str(target)]
    if loras:
        command.extend(["--lora-paths", *[str(item["path"]) for item in loras], "--lora-scales", *[str(item["scale"]) for item in loras]])
    _run_image_process(
        job_id,
        command,
        cwd=APPLICATION_ROOT,
        target=target,
    )
    kind = str(request_body.get("asset_kind") or "").strip()
    reference_angle = "front_full" if kind == "character" else "three_quarter_45"
    return {
        "url":f"/api/result-media?filename={target.name}&subfolder=images", "filename":target.name, "subfolder":"images",
        "generation_workflow":"FLUX.2 Klein 9B 8-bit/8-step", "workflow_mode":"single_3d_reference_baseline",
        "reference_angle":reference_angle, "base_model":"flux2-klein-9b", "quantization":"8-bit", "steps":8,
        "loras":[{"filename":item["filename"], "scale":item["scale"], "sha256":item["sha256"]} for item in loras],
        "lora_index":str(KLEIN9B_TEST_LORA_INDEX_FILE) if loras else "",
    }


def _asset_3d_media_url(path: Path) -> str:
    relative = path.resolve().relative_to(OUTPUT_ROOT)
    return f"/api/result-media?filename={relative.name}&subfolder={relative.parent.as_posix()}"


def _confirmed_asset_3d_baseline(body: dict, kind: str, asset_name: str) -> str:
    project_id = str(body.get("project_id") or "").strip()
    tenant_id = str(body.get("tenant_id") or "").strip()
    user_id = str(body.get("user_id") or "").strip()
    if not project_id or not tenant_id or not user_id:
        raise ValueError("3D资产缺少完整项目身份")
    collection = {"character":"characters", "prop":"props", "scene":"scenes"}[kind]
    with PROJECT_STORE_LOCK:
        project = next((item for item in _load_store().get("projects", [])
                        if str(item.get("id") or "") == project_id
                        and str(item.get("tenant_id") or "") == tenant_id
                        and str(item.get("user_id") or "") == user_id), None)
        if not project:
            raise ValueError("3D资产所属项目不存在")
        assets = project.get("stage_state", {}).get("assets", {}).get("data", {}).get(collection, [])
        asset = next((item for item in assets if str(item.get("name") or "") == asset_name), None)
        if not isinstance(asset, dict):
            raise ValueError("3D资产不属于当前项目")
        confirmed_url = str(asset.get("image_url") or "").strip()
        if not confirmed_url or not str(asset.get("baseline_confirmed_at") or "").strip() or asset.get("confirmation_phase") != "baseline":
            raise ValueError("3D建模必须使用服务端已记录人工确认的定位基准图")
    requested_url = str(body.get("source_baseline_url") or "").strip()
    if requested_url != confirmed_url:
        raise ValueError("3D输入图片与该资产已确认基准图不一致")
    return confirmed_url


def _generate_asset_3d(body: dict, job_id: str) -> dict:
    _assert_image_job_runnable(job_id)
    kind = str(body.get("asset_kind") or "").strip()
    if kind not in {"character", "prop", "scene"}:
        raise ValueError("3D资产类型只支持人物、道具、场景")
    source_baseline_url = str(body.get("source_baseline_url") or "").strip()
    expected_angle = "front_full" if kind == "character" else "three_quarter_45"
    if str(body.get("reference_angle") or "").strip() != expected_angle:
        raise ValueError(f"{kind} 3D输入角度必须标记为 {expected_angle}")
    if not source_baseline_url or body.get("baseline_confirmed") is not True:
        raise ValueError("3D建模必须使用已人工确认的单张定位基准图")
    source_baseline_url = _confirmed_asset_3d_baseline(body, kind, str(body.get("asset_name") or body.get("name") or "").strip())
    if not MFLUX_FLUX2.is_file() or not ASSET_3D_WORKER.is_file() or not TRIPOSR_PYTHON.is_file():
        raise RuntimeError("3D 本地运行环境未安装完整")
    if not TRIPOSR_MODEL.is_file():
        raise RuntimeError("TripoSR 权重不存在")
    project_id = _safe_name(body.get("project_id") or "project")
    asset_name = _safe_name(body.get("asset_name") or body.get("name") or "asset")
    root = OUTPUT_ROOT / "assets3d" / project_id / kind / asset_name
    root.mkdir(parents=True, exist_ok=True)
    reference = root / ("reference_front.png" if kind == "character" else "reference_45.png")
    prompt = str(body.get("prompt") or body.get("asset_prompt") or body.get("asset_name") or "").strip()
    if kind == "character":
        locked_prompt = (
            "One single Chinese character, full body from head to feet, standing neutral A-pose, camera at eye level, "
            "strict zero-degree front-facing full-body view with face, shoulders, torso, pelvis, knees and feet square to camera, complete head, hands and shoes visible, centered, plain neutral gray background, "
            "soft even studio light, stable face, exact garment layers and accessories, no prop, no text, no cropped limbs, no duplicate person. "
            f"CHARACTER: {prompt}"
        )
    elif kind == "prop":
        locked_prompt = (
            "One isolated complete prop, strict 45-degree three-quarter product view, centered, neutral gray seamless background, "
            "soft even studio light, all edges and thickness visible, no person, no hand, no stand, no text, no extra object. "
            f"PROP: {prompt}"
        )
    else:
        locked_prompt = (
            "One coherent empty architectural environment, 45-degree wide establishing view, eye-level camera, complete spatial layout, "
            "stable scale and materials, even physically plausible light, no people, no text, no collage. "
            f"SCENE: {prompt}"
        )
    _assert_image_job_runnable(job_id)
    _update_image_job(job_id, status="processing", phase="klein9b_reference", heartbeat_at=_iso_now(),
                      model="FLUX.2 Klein 9B 8-bit", workflow="asset_3d")
    reference.unlink(missing_ok=True)
    source_baseline = _reference_path(source_baseline_url)
    shutil.copy2(source_baseline, reference)
    _assert_image_job_runnable(job_id)
    _update_image_job(job_id, status="processing", phase="triposr_reconstruct", heartbeat_at=_iso_now(),
                      reference_url=_asset_3d_media_url(reference))
    raw_mesh_path = root / "raw/0/mesh.glb"
    _run_image_process(
        job_id,
        [str(TRIPOSR_PYTHON), str(ASSET_3D_WORKER), "--source", str(reference), "--output", str(root),
         "--kind", kind, "--resolution", "256", "--mode", "reconstruct"],
        cwd=APPLICATION_ROOT,
        target=raw_mesh_path,
        max_attempts=3,
    )
    _assert_image_job_runnable(job_id)
    _update_image_job(job_id, status="processing", phase="mesh_auditing", heartbeat_at=_iso_now(), raw_mesh=str(raw_mesh_path))
    if raw_mesh_path.stat().st_size < 1024:
        raise RuntimeError("TripoSR网格完整性审核失败")
    report_path = root / "report.json"
    report_path.unlink(missing_ok=True)
    _assert_image_job_runnable(job_id)
    _update_image_job(job_id, status="processing", phase="blender_cleanup_render", heartbeat_at=_iso_now())
    _run_image_process(
        job_id,
        [str(TRIPOSR_PYTHON), str(ASSET_3D_WORKER), "--source", str(reference), "--output", str(root),
         "--kind", kind, "--resolution", "256", "--mode", "blender"],
        cwd=APPLICATION_ROOT,
        target=report_path,
        max_attempts=3,
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    dimensions = body.get("dimensions") if isinstance(body.get("dimensions"), dict) else {}
    scene_layout = body.get("scene_layout") if isinstance(body.get("scene_layout"), dict) else {}
    metadata = {
        "asset_id":asset_name, "asset_kind":kind, "project_id":project_id, "version":"1.0",
        "dimensions":dimensions, "dimension_inferred":bool(dimensions.get("inferred", False)),
        "coordinate_system":report.get("coordinate_system"), "origin_policy":report.get("origin_policy"),
        "source_reference":str(reference), "workflow":report.get("workflow"), "face_count":report.get("face_count"),
        "face_limit":report.get("face_limit"), "identity_policy":"3D不执行面部相似度比对；面部一致性只由2D身份审核链锁定",
    }
    if kind == "prop" and str(body.get("asset_type") or "") == "costume":
        metadata.update({
            "asset_type":"costume", "owner":str(body.get("costume_owner") or ""),
            "costume_id":str(body.get("costume_id") or asset_name),
            "costume_version":str(body.get("costume_version") or "v1"),
            "tags":[str(value) for value in body.get("tags", []) if str(value).strip()],
        })
    (root / "metadata.yaml").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    if kind == "scene":
        (root / "layout.yaml").write_text(json.dumps({"coordinate_system":metadata["coordinate_system"], "keyframe":True, **scene_layout}, ensure_ascii=False, indent=2), encoding="utf-8")
        (root / "camera_rig.yaml").write_text(json.dumps({"camera_inherits":False, "angles":report.get("renders", [])}, ensure_ascii=False, indent=2), encoding="utf-8")
    clean_mesh = Path(str(report["clean_mesh"]))
    blend_file = Path(str(report["blend_file"]))
    source_video = Path(str(report["source_video"]))
    renders = [dict(
        item,
        url=_asset_3d_media_url(Path(str(item["path"]))),
        mask_url=_asset_3d_media_url(Path(str(item["mask_path"]))),
        depth_url=_asset_3d_media_url(Path(str(item["depth_path"]))),
        normal_url=_asset_3d_media_url(Path(str(item["normal_path"]))),
    ) for item in report.get("renders", [])]
    return {
        "job_id": job_id, "status": "pending_confirmation", "asset_kind": kind, "asset_name": str(body.get("asset_name") or body.get("name") or ""),
        "reference_url": _asset_3d_media_url(reference), "model_url": _asset_3d_media_url(clean_mesh),
        "blend_url": _asset_3d_media_url(blend_file), "report_url": _asset_3d_media_url(report_path),
        "source_video_url": _asset_3d_media_url(source_video),
        "source_video_spec": dict(report.get("source_video_spec") or {}),
        "renders": renders, "vertex_count": report.get("vertex_count"), "face_count": report.get("face_count"),
        "metadata_path":str(root / "metadata.yaml"), "candidate_path":str(root),
        "workflow": "FLUX.2 Klein 9B 8-bit/8-step -> TripoSR -> Blender 5 headless source video",
        "identity_policy": "人物3D只锁身体服装动作，最终五官由2D身份链覆盖",
        "asset_type": str(body.get("asset_type") or kind),
        "costume_id": str(body.get("costume_id") or ""),
        "costume_version": str(body.get("costume_version") or ""),
    }


def _execute_asset_3d_job(body: dict, job_id: str, subject_key: str) -> None:
    try:
        with _claim_production_resource("3d", job_id, timeout=IMAGE_QUEUE_TIMEOUT_SECONDS, identity=body):
            _assert_image_job_runnable(job_id)
            _require_memory(42 * GIB)
            result = _invoke_production_capability("asset.3d", body=body, job_id=job_id)
        with IMAGE_JOB_LOCK:
            store = _load_image_jobs(); job = store.setdefault("jobs", {}).setdefault(job_id, {})
            if job.get("status") == "failed":
                return
            job.update({"status":"completed", "phase":"completed", "result":result, "finished_at":_iso_now(),
                        "heartbeat_at":_iso_now(), "pid":None, "process_group":None, "error":""})
            _save_image_jobs(store)
    except Exception as error:
        message = f"3D资产生成失败：{str(error)[:500]}"
        current = _load_image_jobs().get("jobs", {}).get(job_id, {})
        if current.get("status") != "failed":
            _update_image_job(job_id, status="failed", phase="failed", error=message, finished_at=_iso_now(),
                              heartbeat_at=_iso_now(), pid=None, process_group=None)
    finally:
        with IMAGE_JOB_LOCK:
            ACTIVE_IMAGE_JOBS.discard(job_id)
            if ACTIVE_IMAGE_SUBJECTS.get(subject_key) == job_id:
                ACTIVE_IMAGE_SUBJECTS.pop(subject_key, None)


def _confirm_asset_3d_job(body: dict) -> dict:
    job_id = str(body.get("job_id") or "")
    project_identity = str(body.get("project_id") or "").strip()
    project_id = _safe_name(project_identity)
    kind = str(body.get("asset_kind") or "")
    asset_identity = str(body.get("asset_name") or "").strip()
    asset_name = _safe_name(asset_identity)
    if not job_id or not project_identity or not project_id or kind not in {"character", "prop", "scene"} or not asset_identity or not asset_name:
        raise ValueError("3D确认参数不完整")
    with IMAGE_JOB_LOCK:
        store = _load_image_jobs(); job = store.get("jobs", {}).get(job_id)
        if not job or job.get("workflow") != "asset_3d" or job.get("status") != "completed":
            raise ValueError("3D候选任务尚未完成")
        expected_subject = f"{project_identity}:3d:{kind}:{asset_identity}"
        if (job.get("asset_kind") != kind or str(job.get("asset_name") or "") != asset_identity
                or str(job.get("subject_key") or "") != expected_subject
                or (job.get("project_id") and str(job.get("project_id")) != project_identity)):
            raise ValueError("3D候选与资产不匹配")
        result = job.get("result") if isinstance(job.get("result"), dict) else None
        if not result or result.get("status") != "pending_confirmation":
            raise ValueError("3D候选不在待确认状态")
        candidate = Path(str(result.get("candidate_path") or OUTPUT_ROOT / "assets3d" / project_id / kind / asset_name)).resolve()
        expected = (OUTPUT_ROOT / "assets3d").resolve()
        if expected not in candidate.parents or not (candidate / "report.json").is_file():
            raise ValueError("3D候选文件不存在")
        is_costume = kind == "prop" and str(job.get("asset_type") or result.get("asset_type") or "") == "costume"
        archive_bucket = "costumes" if is_costume else {"character":"characters", "prop":"props", "scene":"scenes"}[kind]
        archive_id = _safe_name(job.get("costume_id") or result.get("costume_id") or asset_identity) if is_costume else asset_name
        archive_root = APPLICATION_ROOT / "data/hot/projects" / project_id / "3d" / archive_bucket / archive_id
        version_root = archive_root.parent / f"{archive_id}.versions" / datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
        version_root.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(candidate, version_root)
        staged = archive_root.parent / f".{archive_id}.{job_id}.staging"
        if staged.exists(): shutil.rmtree(staged)
        shutil.copytree(candidate, staged)
        backup = archive_root.parent / f".{archive_id}.backup.{job_id}"
        if backup.exists(): shutil.rmtree(backup)
        if archive_root.exists(): archive_root.replace(backup)
        try:
            staged.replace(archive_root)
        except Exception:
            if not archive_root.exists() and backup.exists(): backup.replace(archive_root)
            raise
        if backup.exists():
            previous_version = version_root.parent / f"{version_root.name}.previous"
            backup.replace(previous_version)
        result.update({"status":"completed", "archive_path":str(archive_root), "archive_version":str(version_root),
                       "metadata_path":str(archive_root / "metadata.yaml"), "confirmed_at":_iso_now()})
        job["result"] = result; job["asset_confirmation_status"] = "confirmed"; _save_image_jobs(store)
        return dict(result)


def _recover_asset_3d_archive_backups() -> None:
    hot_root = APPLICATION_ROOT / "data/hot/projects"
    if not hot_root.is_dir(): return
    for backup in hot_root.rglob(".*.backup.*"):
        if not backup.is_dir(): continue
        marker = backup.name.find(".backup.", 1)
        if marker <= 1: continue
        archive_root = backup.parent / backup.name[1:marker]
        if not archive_root.exists():
            backup.replace(archive_root)


def _generate_multireference_shot(name: object, prompt: object, width: object, height: object, references: list[dict], *, job_id: str | None = None) -> dict:
    if not MFLUX_FLUX2_EDIT.is_file():
        raise RuntimeError("FLUX.2多参考图编辑执行器未安装")
    resolved: list[tuple[dict, Path]] = []
    for reference in references:
        if not isinstance(reference, dict) or not reference.get("url"):
            continue
        resolved.append((reference, _reference_path(str(reference["url"]))))
    if not resolved:
        raise RuntimeError("分镜缺少已上传资产参考图")
    clean_root = OUTPUT_ROOT / "temp" / "shot_references" / _safe_name(name)
    clean_root.mkdir(parents=True, exist_ok=True)
    generation_resolved = [(item, source) for item, source in resolved if item.get("usage") != "audit_only"]
    if not generation_resolved:
        raise RuntimeError("分镜缺少可用于推理的主参考图")
    clean_paths: list[Path] = []
    for index, (item, source) in enumerate(generation_resolved, start=1):
        cleaned = clean_root / f"{index:02d}.png"
        usage = str(item.get("usage") or "")
        cleanup_script = (
            "from PIL import Image;import sys;im=Image.open(sys.argv[1]).convert('RGB');w,h=im.size;"
            "im=im.crop((0,int(h*.20),w,max(int(h*.21),int(h*.93)))) if sys.argv[3]=='clothing_body' else im.crop((0,0,w,max(1,int(h*.93))));"
            "im.resize((w,h),Image.Resampling.LANCZOS).save(sys.argv[2])"
        )
        cleanup = subprocess.run(
            [str(COMFY_PYTHON), "-c", cleanup_script, str(source), str(cleaned), usage],
            cwd=APPLICATION_ROOT, capture_output=True, text=True, timeout=120,
        )
        if cleanup.returncode != 0 or not cleaned.is_file():
            raise RuntimeError(f"资产参考图去水印预处理失败：{source.name}")
        clean_paths.append(cleaned)
    target = OUTPUT_ROOT / "images" / f"{_safe_name(name)}.png"
    source_target = OUTPUT_ROOT / "images" / "intermediate" / f"{_safe_name(name)}_multi_reference.png"
    target.parent.mkdir(parents=True, exist_ok=True)
    source_target.parent.mkdir(parents=True, exist_ok=True)
    reference_index = "\n".join(
        f"[IMAGE{index}] = {item.get('kind', 'asset')} {item.get('name', '')} {item.get('angle', '')}; usage={item.get('usage', 'environment_or_prop')}."
        for index, (item, _) in enumerate(generation_resolved, start=1)
    )
    locked_prompt = (
        "Create one single 928x1664 vertical cinematic storyboard frame. The supplied images are reference-only constraints, never objects or panels to reproduce in the final frame.\n"
        f"{reference_index}\n"
        "For each named character, use usage=face_primary as the sole face, makeup, hairline, close-up expression and lip-shape identity source. Never derive, average or blend a face from any other image. Use usage=clothing_body only for body build, garment cut, collar, colors, embroidery, accessories and footwear; its head area has intentionally been removed. Use usage=angle_continuity only to preserve side/back body silhouette, hairstyle length, garment structure and accessories across camera angles; never reproduce those references as extra people or panels. All four references jointly constrain one character. Show each named character exactly once. "
        "Only the named character may wear the clothing colors and silhouette shown in clothing_body. Every unnamed background extra must wear a plain dark charcoal, dark navy or muted brown uniform with no pale cyan, pale green, white hero robe, matching embroidery, matching hairstyle or matching accessories. Extras must have ordinary, mutually different faces and must never resemble the named character. Every visible face must be natural and symmetric, with one pair of eyes, one nose and one mouth. Do not show copies, alternate views, a model sheet, contact sheet, grid, collage, split screen or reference panel. Preserve the named character's exact face shape, facial proportions, hairline, hairstyle and hair length from face_primary. Never transfer one character's face or clothes to another. "
        "Use the scene image as the exact architecture, layout, materials and lighting reference. Use prop images without redesign. "
        "Only pose, expression, camera framing and action may change according to the shot. Render one continuous camera view with one coherent background. No new costume, hairstyle, face, location, text, watermark, duplicate character or extra person.\n"
        f"SHOT REQUIREMENT: {str(prompt or '')}"
    )[:7000]
    command = [
        str(MFLUX_FLUX2_EDIT), "--model", "flux2-klein-4b", "--quantize", "8", "--steps", "4",
        "--image-paths", *[str(path) for path in clean_paths],
        "--width", "512", "--height", "912",
        "--prompt", locked_prompt, "--output", str(source_target),
    ]
    with _claim_production_resource("image", job_id or f"reference-{_safe_name(name)}", timeout=IMAGE_QUEUE_TIMEOUT_SECONDS):
        _require_memory(32 * GIB)
        target.unlink(missing_ok=True)
        source_target.unlink(missing_ok=True)
        _run_image_process(job_id or str(name), command, cwd=APPLICATION_ROOT, target=source_target)
        resize = subprocess.run(
            [str(COMFY_PYTHON), "-c", "from PIL import Image;import sys;im=Image.open(sys.argv[1]).convert('RGB');im.resize((int(sys.argv[3]),int(sys.argv[4])),Image.Resampling.LANCZOS).save(sys.argv[2])", str(source_target), str(target), str(max(512, min(1024, int(width or 928)))), str(max(512, min(1664, int(height or 1664))))],
            cwd=APPLICATION_ROOT, capture_output=True, text=True, timeout=120,
        )
        if resize.returncode != 0 or not target.is_file():
            raise RuntimeError(f"分镜规范尺寸转换失败：{resize.stderr[-300:]}")
        stats = subprocess.run(
            [str(COMFY_PYTHON), "-c", "from PIL import Image,ImageStat;import json,sys;im=Image.open(sys.argv[1]).convert('RGB');s=ImageStat.Stat(im);print(json.dumps({'mean':sum(s.mean)/3,'variance':sum(s.var)/3}))", str(target)],
            cwd=APPLICATION_ROOT, capture_output=True, text=True, timeout=60, check=True,
        )
        evidence = json.loads(stats.stdout.strip())
        if float(evidence.get("mean", 0)) < 2.0 or float(evidence.get("variance", 0)) < 4.0:
            target.unlink(missing_ok=True)
            raise RuntimeError(f"分镜输出为空白图或纯黑图：{json.dumps(evidence, ensure_ascii=False)}")
        face_primaries = [(item, source) for item, source in resolved if item.get("usage") == "face_primary"]
        if len(face_primaries) == 1:
            _apply_storyboard_face_lock(target, face_primaries[0][1], str(name), job_id=job_id)
    return {
        "url":f"/api/result-media?filename={target.name}&subfolder=images", "filename":target.name, "subfolder":"images",
        "generation_workflow":"FLUX.2 Klein 4B role-separated reference edit", "identity_lock":"single_front_face_primary",
        "reference_count":len(generation_resolved), "audit_reference_count":len(resolved), "reference_manifest":[{"name":item.get("name"), "kind":item.get("kind"), "angle":item.get("angle"), "usage":item.get("usage")} for item, _ in resolved],
        "generation_resolution":[512,912], "delivery_resolution":[max(512, min(1024, int(width or 928))), max(512, min(1664, int(height or 1664)))],
    }


def _apply_storyboard_face_lock(target: Path, face_reference: Path, name: str, *, job_id: str | None = None) -> None:
    _start_comfy()
    input_name = f"short_drama_shot_faces/{uuid4().hex}_shot.png"
    source_name = f"short_drama_shot_faces/{uuid4().hex}_source.png"
    input_path = COMFY_INPUT / input_name
    source_path = COMFY_INPUT / source_name
    input_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(target, input_path)
    shutil.copy2(face_reference, source_path)
    prefix = f"short_drama/{_safe_name(name)}_face_locked_{uuid4().hex[:8]}"
    graph = {
        "1":{"class_type":"LoadImage","inputs":{"image":input_name}},
        "2":{"class_type":"LoadImage","inputs":{"image":source_name}},
        "3":{"class_type":"ReActorFaceSwap","inputs":{
            "enabled":True,"input_image":["1",0],"source_image":["2",0],"swap_model":"inswapper_128.onnx",
            "facedetection":"retinaface_resnet50","face_restore_model":"none","face_restore_visibility":1.0,
            "codeformer_weight":0.5,"detect_gender_input":"no","detect_gender_source":"no",
            "input_faces_index":"0","source_faces_index":"0","console_log_level":1,
        }},
        "4":{"class_type":"SaveImage","inputs":{"images":["3",0],"filename_prefix":prefix}},
    }
    prompt_id = ""
    try:
        request = Request(f"{COMFY_API}/prompt", data=json.dumps({"prompt":graph}).encode(), headers={"Content-Type":"application/json"}, method="POST")
        with urlopen(request, timeout=1900) as response:
            prompt_id = str(json.loads(response.read())["prompt_id"])
        if job_id:
            _update_image_job(job_id, status="processing", stage="storyboard_face_lock", comfy_prompt_id=prompt_id, heartbeat_at=_iso_now())
        deadline = time.time() + 600
        while time.time() < deadline:
            time.sleep(2)
            with urlopen(f"{COMFY_API}/history/{prompt_id}", timeout=30) as response:
                history = json.loads(response.read())
            record = history.get(prompt_id)
            if not record:
                continue
            status = record.get("status", {})
            if status.get("status_str") == "error":
                raise RuntimeError("分镜人脸身份对齐执行失败")
            outputs = record.get("outputs", {}).get("4", {}).get("images", [])
            if outputs:
                output = outputs[0]
                produced = COMFY_OUTPUT / str(output.get("subfolder", "")) / str(output["filename"])
                if produced.is_file():
                    shutil.copy2(produced, target)
                    return
        raise RuntimeError("分镜人脸身份对齐超时")
    finally:
        if prompt_id:
            _cancel_comfy_prompt(prompt_id)
        input_path.unlink(missing_ok=True)
        source_path.unlink(missing_ok=True)
        _free_comfy_memory()


def _audit_shot_consistency(body: dict) -> dict:
    candidate = _reference_path(str(body.get("image_url", "")))
    references = [item for item in body.get("references", []) if isinstance(item, dict) and item.get("url")]
    expected_characters = [str(item) for item in body.get("expected_characters", []) if str(item).strip()]
    if not references:
        return {"passed":False, "summary":"缺少资产一致性参考图", "missing_subjects":expected_characters, "contradictions":["no_asset_references"]}
    selected = references[:12]
    raw_images = [candidate, *[_reference_path(str(item["url"])) for item in selected]]
    audit_root = OUTPUT_ROOT / "temp" / "shot_audit"
    audit_root.mkdir(parents=True, exist_ok=True)
    images: list[Path] = []
    for index, source in enumerate(raw_images):
        prepared = audit_root / f"{hashlib.sha256(f'{candidate}:{index}:{source}'.encode()).hexdigest()[:20]}.jpg"
        prepare = subprocess.run(
            [str(COMFY_PYTHON), "-c", "from PIL import Image;import sys;im=Image.open(sys.argv[1]).convert('RGB');im.thumbnail((640,960),Image.Resampling.LANCZOS);im.save(sys.argv[2],quality=82,optimize=True)", str(source), str(prepared)],
            cwd=APPLICATION_ROOT, capture_output=True, text=True, timeout=120,
        )
        if prepare.returncode != 0 or not prepared.is_file():
            return {"passed":False, "summary":"一致性审核图片预处理失败", "missing_subjects":expected_characters, "contradictions":["audit_image_prepare_failed"]}
        images.append(prepared)
    manifest = "\n".join(f"Reference {index}: {item.get('kind')} {item.get('name')} {item.get('angle')}" for index, item in enumerate(selected, start=1))
    prompt = f"""Image 1 is a generated storyboard frame. Images 2 onward are mandatory approved asset references.
{manifest}
Expected visual: {str(body.get('expected_visual', ''))}
Expected characters: {', '.join(expected_characters)}
Return strict JSON only: {{"passed":true,"face_consistent":true,"hair_consistent":true,"clothing_consistent":true,"body_consistent":true,"scene_consistent":true,"prop_consistent":true,"single_continuous_frame":true,"no_duplicate_expected_character":true,"no_text_or_watermark":true,"faces_anatomically_valid":true,"hands_anatomically_valid":true,"body_anatomically_valid":true,"missing_subjects":[],"contradictions":[],"summary":""}}.
Fail if any expected character is missing, duplicated, shown as multiple views, or has a different face shape or facial features, changed hairstyle, changed body build, changed garment cut/color/decoration/footwear. Fail for melted, asymmetrical, duplicated or misplaced facial features; fused, missing, extra or malformed fingers/hands; extra, fused, disconnected or unnaturally bent limbs; broken joints or distorted body proportions. Also fail if the result is a collage, grid, split screen or character sheet, if the scene architecture/layout/material differs, if a required prop is redesigned, or if any caption, label, Chinese/English text, pseudo-text, rune-like gibberish, logo, signature, watermark or AI-generation mark appears unless the expected visual explicitly requires non-linguistic magical symbols. Occluded features are not failures, but visible contradictions are. Every boolean field must be explicitly true to pass."""
    try:
        request = Request("http://127.0.0.1:11434/api/generate", data=json.dumps({
            "model":"llava:latest", "prompt":prompt,
            "images":[base64.b64encode(path.read_bytes()).decode("ascii") for path in images],
            "stream":False, "keep_alive":0, "format":"json", "options":{"num_ctx":8192,"num_predict":320,"temperature":0,"seed":73},
        }).encode("utf-8"), headers={"Content-Type":"application/json"}, method="POST")
        with urlopen(request, timeout=900) as response:
            result = json.loads(str(json.loads(response.read()).get("response", "{}")))
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:300]
        return {"passed":False, "summary":f"一致性审核失败：{detail}", "missing_subjects":expected_characters, "contradictions":["audit_unavailable"]}
    except Exception as error:
        return {"passed":False, "summary":f"一致性审核失败：{str(error)[:180]}", "missing_subjects":expected_characters, "contradictions":["audit_unavailable"]}
    fields = ("face_consistent", "hair_consistent", "clothing_consistent", "body_consistent", "scene_consistent", "prop_consistent", "single_continuous_frame", "no_duplicate_expected_character", "no_text_or_watermark", "faces_anatomically_valid", "hands_anatomically_valid", "body_anatomically_valid")
    passed = bool(result.get("passed")) and all(result.get(field) is True for field in fields)
    result["passed"] = passed
    result.setdefault("missing_subjects", [])
    result.setdefault("contradictions", [])
    result.setdefault("summary", "一致性验收通过" if passed else "人物或场景一致性未通过")
    face_primary_refs = {
        str(item.get("name")): _reference_path(str(item["url"]))
        for item in references
        if item.get("kind") == "character" and item.get("usage") == "face_primary" and item.get("name") in expected_characters
    }
    if face_primary_refs:
        identity_script = r'''import cv2,json,sys,numpy as np
from insightface.app import FaceAnalysis
candidate=cv2.imread(sys.argv[1]); refs=json.loads(sys.argv[2]); models=sys.argv[3]
app=FaceAnalysis(name="buffalo_l",root=models,providers=["CPUExecutionProvider"]);app.prepare(ctx_id=-1,det_size=(1024,1024))
def faces(path_or_image):
 image=cv2.imread(path_or_image) if isinstance(path_or_image,str) else path_or_image
 if image is None:return []
 h,w=image.shape[:2]
 if max(h,w)<1400:image=cv2.resize(image,None,fx=2,fy=2,interpolation=cv2.INTER_CUBIC)
 return app.get(image)
candidate_faces=faces(candidate);out={};sym=[]
for index,face in enumerate(candidate_faces):
 k=np.asarray(face.kps,dtype=np.float32);eye=max(float(np.linalg.norm(k[1]-k[0])),1.0);mouth=max(float(np.linalg.norm(k[4]-k[3])),1.0)
 eye_delta=abs(float(k[1,1]-k[0,1]))/eye;mouth_delta=abs(float(k[4,1]-k[3,1]))/mouth
 sym.append({"face":index,"eye_vertical_ratio":eye_delta,"mouth_vertical_ratio":mouth_delta,"passed":eye_delta<=.22 and mouth_delta<=.28})
for name,path in refs.items():
 rf=faces(path)
 if not rf:out[name]={"passed":False,"reason":"reference_face_missing","matches":0,"scores":[]};continue
 ref=max(rf,key=lambda f:float((f.bbox[2]-f.bbox[0])*(f.bbox[3]-f.bbox[1]))).normed_embedding
 ref=np.asarray(ref,dtype=np.float32);ref/=max(float(np.linalg.norm(ref)),1e-8)
 scores=[]
 for face in candidate_faces:
  vec=np.asarray(face.normed_embedding,dtype=np.float32);vec/=max(float(np.linalg.norm(vec)),1e-8);scores.append(float(np.dot(ref,vec)))
 matches=sum(score>=.40 for score in scores);best=max(scores,default=-1.0)
 out[name]={"passed":matches==1 and best>=.40,"matches":matches,"best_similarity":best,"scores":scores}
print(json.dumps({"characters":out,"face_symmetry":sym,"detected_faces":len(candidate_faces)},ensure_ascii=False))
'''
        try:
            identity_run = subprocess.run(
                [str(COMFY_PYTHON), "-c", identity_script, str(candidate), json.dumps({name:str(path) for name,path in face_primary_refs.items()}, ensure_ascii=False), "/Users/aoo/AI/Models/Vision/InsightFace"],
                capture_output=True, text=True, timeout=300, check=True,
            )
            identity_result = json.loads(identity_run.stdout.strip().splitlines()[-1])
        except Exception as error:
            identity_result = {"error":str(error)[:180]}
        result["identity_face_audit"] = identity_result
        invalid_identities = [name for name, evidence in identity_result.get("characters", {}).items() if evidence.get("passed") is not True]
        asymmetric_faces = [item for item in identity_result.get("face_symmetry", []) if item.get("passed") is not True]
        if invalid_identities or asymmetric_faces or identity_result.get("error"):
            result["passed"] = False
            result["contradictions"] = [
                *result.get("contradictions", []),
                *[f"identity_missing_or_duplicated:{name}" for name in invalid_identities],
                *(["visible_face_asymmetry"] if asymmetric_faces else []),
                *(["identity_audit_unavailable"] if identity_result.get("error") else []),
            ]
            result["summary"] = "人脸身份、重复人物或五官对称专项验收未通过"
    character_refs = [item for item in references if item.get("kind") == "character" and item.get("usage") in {"face_primary", "clothing_body", "angle_continuity"}]
    if expected_characters and character_refs:
        duplicate_paths = [candidate, *[_reference_path(str(item["url"])) for item in character_refs[:8]]]
        duplicate_manifest = "；".join(f"Reference {index + 1}={item.get('name')} {item.get('angle')}" for index, item in enumerate(character_refs[:8]))
        duplicate_prompt = (
            "Image 1 is the generated frame. Remaining images identify the named main characters. "
            f"{duplicate_manifest}. Expected named characters: {', '.join(expected_characters)}. "
            "Inspect Image 1 only and return strict JSON: {\"duplicate_expected_character\":false,\"missing_expected_character\":false,\"count_explanation\":\"\"}. "
            "duplicate_expected_character must be true if the same named character identity or the same distinctive main costume appears more than once, including front/side/back copies. "
            "Unnamed background extras in clearly different dark uniforms are allowed."
        )
        try:
            duplicate_request = Request("http://127.0.0.1:11434/api/generate", data=json.dumps({
                "model":"llava:latest", "prompt":duplicate_prompt,
                "images":[base64.b64encode(path.read_bytes()).decode("ascii") for path in duplicate_paths],
                "stream":False, "keep_alive":0, "format":"json", "options":{"num_ctx":8192,"num_predict":160,"temperature":0,"seed":97},
            }).encode("utf-8"), headers={"Content-Type":"application/json"}, method="POST")
            with urlopen(duplicate_request, timeout=600) as response:
                duplicate_result = json.loads(str(json.loads(response.read()).get("response", "{}")))
        except Exception as error:
            duplicate_result = {"duplicate_expected_character":True, "missing_expected_character":True, "count_explanation":f"重复人物审核失败：{str(error)[:120]}"}
        result["duplicate_audit"] = duplicate_result
        if duplicate_result.get("duplicate_expected_character") is not False or duplicate_result.get("missing_expected_character") is not False:
            result["passed"] = False
            result["contradictions"] = [*result.get("contradictions", []), "duplicate_or_missing_expected_character"]
            result["summary"] = str(duplicate_result.get("count_explanation") or "同一角色重复出现或缺失")
        full_body_by_name = {}
        for item in character_refs:
            if item.get("angle") == "全身" and item.get("name") in expected_characters:
                full_body_by_name[str(item.get("name"))] = _reference_path(str(item["url"]))
        if full_body_by_name:
            costume_script = r'''import cv2,json,sys,numpy as np
from ultralytics import YOLO
candidate=cv2.imread(sys.argv[1]); refs=json.loads(sys.argv[2]); model=YOLO("/Users/aoo/AI/ComfyUI-Shared/models/yolo11n.pt")
def people(image):
 r=model(image,verbose=False)[0]; return [[int(v) for v in box] for cls,conf,box in zip(r.boxes.cls,r.boxes.conf,r.boxes.xyxy) if int(cls)==0 and float(conf)>=0.20]
def hist(image,box):
 x1,y1,x2,y2=box; w=max(1,x2-x1);h=max(1,y2-y1); crop=image[y1+int(h*.24):y1+int(h*.82),x1+int(w*.12):x2-int(w*.12)]
 if crop.size==0:return None
 hsv=cv2.cvtColor(crop,cv2.COLOR_BGR2HSV); out=cv2.calcHist([hsv],[0,1,2],None,[18,6,6],[0,180,0,256,0,256]);lab=cv2.cvtColor(crop,cv2.COLOR_BGR2LAB);return cv2.normalize(out,out).flatten(),cv2.mean(lab)[:3]
cboxes=people(candidate); ch=[hist(candidate,b) for b in cboxes];out={}
for name,path in refs.items():
 image=cv2.imread(path); boxes=people(image)
 if not boxes:out[name]={"matches":0,"scores":[]};continue
 ref=hist(image,max(boxes,key=lambda b:(b[2]-b[0])*(b[3]-b[1])));scores=[float(cv2.compareHist(ref[0],h[0],cv2.HISTCMP_CORREL)) for h in ch if h is not None];labs=[h[1] for h in ch if h is not None]
 max_l=max((v[0] for v in labs),default=0);color_matches=sum(v[0]>=max_l-10 and abs(v[1]-ref[1][1])<=8 and abs(v[2]-ref[1][2])<=8 for v in labs)
 out[name]={"matches":max(sum(s>=.72 for s in scores),color_matches),"scores":scores,"lab_means":labs,"reference_lab":ref[1]}
print(json.dumps(out,ensure_ascii=False))
'''
            try:
                costume_run = subprocess.run([str(COMFY_PYTHON), "-c", costume_script, str(candidate), json.dumps({name:str(path) for name,path in full_body_by_name.items()}, ensure_ascii=False)], capture_output=True, text=True, timeout=240, check=True)
                costume_result = json.loads(costume_run.stdout.strip().splitlines()[-1])
            except Exception as error:
                costume_result = {"error":str(error)[:180]}
            result["costume_duplicate_audit"] = costume_result
            duplicates = [name for name, evidence in costume_result.items() if isinstance(evidence, dict) and int(evidence.get("matches", 0)) > 1]
            if duplicates:
                result["passed"] = False
                result["contradictions"] = [*result.get("contradictions", []), *[f"duplicate_costume_identity:{name}" for name in duplicates]]
                result["summary"] = f"同一角色服装身份重复出现：{'、'.join(duplicates)}"
    return result


def _remote_cuda_image(provider: str, endpoint: str, token: str, payload: dict, target: Path) -> dict:
    headers = {"Content-Type":"application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(endpoint, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    try:
        with urlopen(request, timeout=3600) as response:
            result = json.loads(response.read())
    except Exception as error:
        raise RuntimeError(f"{provider}远程CUDA服务调用失败：{str(error)[:300]}") from error
    encoded = str(result.get("image_base64") or "").strip()
    remote_url = str(result.get("image_url") or "").strip()
    if encoded.startswith("data:"):
        encoded = encoded.split(",", 1)[-1]
    try:
        content = base64.b64decode(encoded, validate=True) if encoded else urlopen(remote_url, timeout=600).read() if remote_url else b""
    except Exception as error:
        raise RuntimeError(f"{provider}返回图片无法读取：{str(error)[:300]}") from error
    if not content.startswith(b"\x89PNG\r\n\x1a\n") and not content.startswith(b"\xff\xd8\xff"):
        raise RuntimeError(f"{provider}未返回有效PNG或JPEG图片")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    return result


def _generate_visual_persona_front_full(name: object, prompt: object, reference_url: str, *, character_gender: str = "", job_id: str | None = None) -> dict:
    if not VISUAL_PERSONA_LICENSE_APPROVED:
        raise RuntimeError("Visual Persona权重许可证尚未获生产批准，正面全身生成已阻断")
    if not VISUAL_PERSONA_API_URL:
        raise RuntimeError("未配置Visual Persona远程CUDA服务，正面全身生成已阻断")
    source = _reference_path(reference_url)
    pose = APPLICATION_ROOT / "plugins/builtin/short_drama/backend/assets/character_controls/openpose_front_full_7_5.png"
    target = OUTPUT_ROOT / "images" / f"{_safe_name(name)}.png"
    if job_id:
        _update_image_job(job_id, status="processing", stage="visual_persona_front_full", heartbeat_at=_iso_now())
    payload = {
        "mode":"pose_guided_full_body", "model":"Visual-Persona-CVPR2025", "width":928, "height":1664,
        "reference_image_base64":base64.b64encode(source.read_bytes()).decode("ascii"),
        "pose_image_base64":base64.b64encode(pose.read_bytes()).decode("ascii"),
        "prompt":str(prompt or "")[:3000], "character_gender":character_gender,
        "requirements":{"head_to_body_ratio":[7.0,7.8],"front_yaw_degrees":[-3,3],"bottom_margin_percent":[4,6],"plain_background":True},
    }
    result = _remote_cuda_image("Visual Persona", VISUAL_PERSONA_API_URL, VISUAL_PERSONA_API_TOKEN, payload, target)
    return {"url":f"/api/result-media?filename={target.name}&subfolder=images","filename":target.name,"subfolder":"images",
            "workflow_mode":"visual_persona_pose_guided_front_full","base_model":"SDXL","identity_model":"Visual Persona",
            "remote_model_version":result.get("model_version"),"reference_url":reference_url,"target_pose":"front_full",
            "width":928,"height":1664,"requires_full_body_confirmation":True}


def _generate_pshuman_view(name: object, prompt: object, identity_url: str, full_body_url: str, target_pose: str, *, job_id: str | None = None) -> dict:
    if not PSHUMAN_LICENSE_APPROVED:
        raise RuntimeError("PSHuman及其依赖权重许可证尚未获生产批准，多视图生成已阻断")
    if not PSHUMAN_API_URL:
        raise RuntimeError("未配置PSHuman远程CUDA服务，多视图生成已阻断")
    if target_pose not in {"side_90_full", "back_full"}:
        raise RuntimeError(f"PSHuman不支持的目标角度：{target_pose}")
    identity = _reference_path(identity_url)
    full_body = _reference_path(full_body_url)
    target = OUTPUT_ROOT / "images" / f"{_safe_name(name)}.png"
    azimuth = 90 if target_pose == "side_90_full" else 180
    if job_id:
        _update_image_job(job_id, status="processing", stage="pshuman_multiview", heartbeat_at=_iso_now())
    payload = {
        "mode":"reconstruct_and_render", "model":"PSHuman_Unclip_768_6views", "azimuth_degrees":azimuth,
        "elevation_degrees":0, "width":928, "height":1664,
        "identity_image_base64":base64.b64encode(identity.read_bytes()).decode("ascii"),
        "full_body_image_base64":base64.b64encode(full_body.read_bytes()).decode("ascii"),
        "prompt":str(prompt or "")[:3000], "background":"plain neutral gray",
        "requirements":{"bottom_margin_percent":[4,6],"preserve_mesh_and_texture":True},
    }
    result = _remote_cuda_image("PSHuman", PSHUMAN_API_URL, PSHUMAN_API_TOKEN, payload, target)
    return {"url":f"/api/result-media?filename={target.name}&subfolder=images","filename":target.name,"subfolder":"images",
            "workflow_mode":"pshuman_shared_mesh_render","base_model":"PSHuman_Unclip_768_6views",
            "remote_model_version":result.get("model_version"),"reference_url":identity_url,"clothing_reference_url":full_body_url,
            "target_pose":target_pose,"azimuth_degrees":azimuth,"width":928,"height":1664}


def _schnell_test_loras(body: dict) -> list[dict]:
    if str(body.get("asset_phase", "")) == "variant":
        return []
    project_id = str(body.get("project_id", ""))
    project = next((item for item in _load_store().get("projects", []) if str(item.get("id", "")) == project_id), {})
    project_style = str(project.get("style", "") or project.get("category", "") or "国风浅涂").strip()
    root = LORA_ROOT / project_style
    if not root.is_dir():
        root = LORA_ROOT / "国风浅涂"
    subject = str(body.get("asset_subject", "")).split(":", 1)[0]
    kind = str(body.get("asset_kind", ""))
    if kind == "prop":
        return []
    style_paths = sorted((root / "风格LoRA").glob("*FLUX1_Schnell_商用.safetensors"))
    if not style_paths:
        approved_test_style = {
            "国风浅涂":"风格_国风仙韵_FLUX1_仅测试.safetensors",
        }.get(project_style, "")
        approved_path = root / "风格LoRA" / approved_test_style
        style_paths = [approved_path] if approved_test_style and approved_path.is_file() else []
    if not style_paths:
        return []
    # Keep one project-wide style, but exclude mislabeled portrait-heavy weights
    # whose training metadata overrides requested character gender.
    neutral_styles = [path for path in style_paths if any(token in path.name for token in ("幻彩仙境", "暗夜仙境", "流沙仙境"))]
    style_pool = neutral_styles or style_paths
    style_path = style_pool[int(hashlib.sha256(project_id.encode()).hexdigest()[:8], 16) % len(style_pool)]
    selected = [{"kind":"style", "path":style_path, "scale":0.35}]
    category = "人物LoRA" if kind == "character" else "灵兽LoRA" if kind == "animal" else ""
    if category:
        candidates = sorted((root / category).glob("*FLUX1_Schnell_商用.safetensors"))
        if kind == "character":
            female_names = ("汉服仙姝", "清颜仙姝", "自然仙姝", "灵秀仙姝", "群芳仙姝")
            # Metadata audit: 温润仙君 contains only female training captions and
            # 古风仙君 is also female-heavy. Use the verified male-biased weight.
            male_names = ("写实仙君",)
            gender = str(body.get("character_gender", "")).strip().lower()
            prompt = str(body.get("prompt", "")).lower()
            female = gender in {"女", "女性", "female", "woman", "girl", "f"} or (
                not gender and any(token in prompt for token in ("女性", "女人", "女孩", "少女", "女主", "female", "woman", "girl"))
            )
            names = female_names if female else male_names
            candidates = [path for path in candidates if any(item in path.name for item in names)]
        candidates = [path for path in candidates if not os.path.samefile(path, style_path)]
        if candidates:
            selected.append({"kind":"character" if kind == "character" else "animal", "path":candidates[int(hashlib.sha256(f'{project_id}:{subject}'.encode()).hexdigest()[:8], 16) % len(candidates)], "scale":0.20 if kind == "character" else 0.30})
    return selected


def _generate_flux1_schnell_baseline(name: object, prompt: object, width: object, height: object, body: dict, *, job_id: str | None = None) -> dict:
    """Generate through the live ComfyUI FLUX.1 Schnell GGUF service."""
    width_value = max(512, min(1024, int(width or 928))) // 16 * 16
    height_value = max(512, min(1664, int(height or 1664))) // 16 * 16
    target = OUTPUT_ROOT / "images" / f"{_safe_name(name)}.png"
    schnell_target = OUTPUT_ROOT / "images" / "intermediate" / f"{_safe_name(name)}_schnell.png"
    target.parent.mkdir(parents=True, exist_ok=True)
    schnell_target.parent.mkdir(parents=True, exist_ok=True)
    loras = _schnell_test_loras(body)
    model_output: list[object] = ["1", 0]
    clip_output: list[object] = ["2", 0]
    graph: dict[str, dict] = {
        "1":{"class_type":"UnetLoaderGGUF","inputs":{"unet_name":"flux1-schnell-Q8_0.gguf"}},
        "2":{"class_type":"DualCLIPLoader","inputs":{"clip_name1":"clip_l.safetensors","clip_name2":"t5xxl_fp8_e4m3fn_scaled.safetensors","type":"flux"}},
    }
    for index, item in enumerate(loras, start=10):
        graph[str(index)] = {"class_type":"LoraLoader","inputs":{"model":model_output,"clip":clip_output,"lora_name":str(item["path"].relative_to(LORA_ROOT)),"strength_model":item["scale"],"strength_clip":item["scale"]}}
        model_output, clip_output = [str(index), 0], [str(index), 1]
    gender = str(body.get("character_gender", ""))
    gender_lock = "adult Chinese man, unmistakably male, masculine facial structure, male hairline, no woman, no feminine face. " if str(body.get("asset_kind", "")) == "character" and "男" in gender else ""
    graph.update({
        "3":{"class_type":"CLIPTextEncode","inputs":{"clip":clip_output,"text":f"{gender_lock}{str(prompt or 'cinematic vertical film asset')}"}},
        "4":{"class_type":"EmptySD3LatentImage","inputs":{"width":width_value,"height":height_value,"batch_size":1}},
        "5":{"class_type":"ModelSamplingFlux","inputs":{"model":model_output,"max_shift":1.15,"base_shift":0.5,"width":width_value,"height":height_value}},
        "6":{"class_type":"KSampler","inputs":{"model":["5",0],"seed":int(time.time_ns() % 2**32),"steps":4,"cfg":1.0,"sampler_name":"euler","scheduler":"simple","positive":["3",0],"negative":["3",0],"latent_image":["4",0],"denoise":1.0}},
        "7":{"class_type":"VAELoader","inputs":{"vae_name":"ae.safetensors"}},
        "8":{"class_type":"VAEDecode","inputs":{"samples":["6",0],"vae":["7",0]}},
        "9":{"class_type":"SaveImage","inputs":{"images":["8",0],"filename_prefix":f"short_drama/{_safe_name(name)}"}},
    })
    with _claim_production_resource("image", job_id or f"schnell-{_safe_name(name)}", timeout=IMAGE_QUEUE_TIMEOUT_SECONDS):
        _require_memory(32 * GIB)
        try:
            request = Request(f"{COMFY_API}/prompt", data=json.dumps({"prompt":graph}).encode(), headers={"Content-Type":"application/json"}, method="POST")
            with urlopen(request, timeout=30) as response:
                prompt_id = json.loads(response.read())["prompt_id"]
        except Exception:
            _free_comfy_memory()
            raise
        if job_id:
            _update_image_job(job_id, status="generating", stage="schnell_generating", schnell_prompt_id=prompt_id, heartbeat_at=_iso_now())
        deadline = time.time() + 900
        try:
            while time.time() < deadline:
                time.sleep(2)
                if job_id:
                    current_job = _load_image_jobs().get("jobs", {}).get(job_id, {})
                    if current_job.get("status") == "failed":
                        _cancel_comfy_prompt(prompt_id)
                        raise RuntimeError(str(current_job.get("error") or "图片任务已停止"))
                    _update_image_job(job_id, heartbeat_at=_iso_now(), stage="schnell_generating")
                with urlopen(f"{COMFY_API}/history/{prompt_id}", timeout=30) as response:
                    history = json.loads(response.read())
                if prompt_id not in history:
                    continue
                record = history[prompt_id]
                if record.get("status", {}).get("status_str") != "success":
                    raise RuntimeError(f"Schnell GGUF 生图失败：{str(record.get('status', {}).get('messages', []))[-500:]}")
                output = record["outputs"]["9"]["images"][0]
                generated = COMFY_OUTPUT / output.get("subfolder", "") / output["filename"]
                shutil.copy2(generated, schnell_target)
                break
            else:
                raise RuntimeError("Schnell GGUF 生图超时")
        finally:
            if 'prompt_id' in locals():
                _cancel_comfy_prompt(prompt_id)
            _free_comfy_memory()
        # Baseline generation must finish when Schnell finishes. Qwen-Edit is an
        # explicit editing operation only; chaining it here turns a seconds-long
        # baseline into a long-running task and can monopolize the shared queue.
        temporary_target = target.with_suffix(f".{uuid4().hex}.tmp.png")
        shutil.copy2(schnell_target, temporary_target)
        os.replace(temporary_target, target)
        return {
            "url":f"/api/result-media?filename={target.name}&subfolder=images", "filename":target.name, "subfolder":"images",
            "generation_workflow":"FLUX.1 Schnell GGUF Q8_0", "workflow_mode":"single_model_baseline",
            "lora":({"id":"schnell-gguf-q8-locked", "style":"项目固定Schnell风格LoRA", "scale":loras[0]["scale"], "base_model":"flux1-schnell-Q8_0.gguf"}
                    if loras else {"id":"none", "style":"项目提示词锁定", "scale":0, "base_model":"flux1-schnell-Q8_0.gguf"}),
            "loras":[{"kind":item["kind"], "path":str(item["path"]), "scale":item["scale"]} for item in loras],
            "schnell_intermediate":str(schnell_target),
        }


def _write_qwen_repair_mask(target: Path, width: int, height: int, asset_kind: str) -> None:
    """Write a real grayscale noise mask without loading another model."""
    inset = 0.16 if asset_kind == "scene" else 0.10
    left, right = int(width * inset), int(width * (1 - inset))
    top, bottom = int(height * inset), int(height * (1 - inset))
    rows = []
    for y in range(height):
        row = bytearray(width)
        if top <= y < bottom:
            row[left:right] = b"\xff" * (right - left)
        rows.append(b"\x00" + bytes(row))
    raw = b"".join(rows)
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    target.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def _repair_schnell_output_with_qwen(source: Path, target: Path, prompt: str, width: int, height: int, name: object, *, job_id: str | None = None, asset_kind: str = "") -> dict:
    """Run Qwen-Edit as a separate workflow after the Schnell image is persisted."""
    if not source.is_file():
        raise RuntimeError("Schnell 中间成品图不存在，禁止启动 Qwen-Edit 修复")
    input_name = f"short_drama_qwen_repairs/{uuid4().hex}{source.suffix.lower()}"
    mask_name = f"short_drama_qwen_repairs/{uuid4().hex}_mask.png"
    input_path = COMFY_INPUT / input_name
    mask_path = COMFY_INPUT / mask_name
    input_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, input_path)
    _write_qwen_repair_mask(mask_path, width, height, asset_kind)
    target.unlink(missing_ok=True)
    repair_prompt = (
        "仅对输入成品图执行局部瑕疵修复。修复畸形五官、异常眼睛、错误手指、肢体粘连、破损服装纹样、"
        "重复物体和明显生成伪影；未出现问题的区域必须保持原样。严格保持主体身份、脸型、发型、服装、"
        "姿态、构图、背景、光影、色彩和项目画风，不得重新设计、换脸、换装、增删主体或改变镜头。"
        f"原始资产要求：{prompt[:900]}"
    )
    graph = {
        "1":{"class_type":"LoadImage","inputs":{"image":input_name}},
        "2":{"class_type":"FluxKontextImageScale","inputs":{"image":["1",0]}},
        "3":{"class_type":"UNETLoader","inputs":{"unet_name":"qwen_image_edit_2511_bf16.safetensors","weight_dtype":"default"}},
        "4":{"class_type":"ModelSamplingAuraFlow","inputs":{"model":["3",0],"shift":3.1}},
        "5":{"class_type":"CFGNorm","inputs":{"model":["4",0],"strength":1.0}},
        "6":{"class_type":"CLIPLoader","inputs":{"clip_name":"qwen_2.5_vl_7b_fp8_scaled.safetensors","type":"qwen_image","device":"default"}},
        "7":{"class_type":"VAELoader","inputs":{"vae_name":"qwen_image_vae.safetensors"}},
        "8":{"class_type":"TextEncodeQwenImageEditPlus","inputs":{"clip":["6",0],"vae":["7",0],"image1":["2",0],"prompt":repair_prompt}},
        "9":{"class_type":"TextEncodeQwenImageEditPlus","inputs":{"clip":["6",0],"vae":["7",0],"image1":["2",0],"prompt":""}},
        "10":{"class_type":"FluxKontextMultiReferenceLatentMethod","inputs":{"conditioning":["8",0],"reference_latents_method":"index_timestep_zero"}},
        "11":{"class_type":"FluxKontextMultiReferenceLatentMethod","inputs":{"conditioning":["9",0],"reference_latents_method":"index_timestep_zero"}},
        "12":{"class_type":"VAEEncode","inputs":{"pixels":["2",0],"vae":["7",0]}},
        "16":{"class_type":"LoadImageMask","inputs":{"image":mask_name,"channel":"red"}},
        "17":{"class_type":"SetLatentNoiseMask","inputs":{"samples":["12",0],"mask":["16",0]}},
        "13":{"class_type":"KSampler","inputs":{"model":["5",0],"seed":int(time.time_ns() % 2**32),"steps":8,"cfg":4.0,"sampler_name":"euler","scheduler":"simple","positive":["10",0],"negative":["11",0],"latent_image":["17",0],"denoise":0.45}},
        "14":{"class_type":"VAEDecode","inputs":{"samples":["13",0],"vae":["7",0]}},
        "15":{"class_type":"SaveImage","inputs":{"images":["14",0],"filename_prefix":f"short_drama/{_safe_name(name)}_qwen_repaired"}},
    }
    try:
        _wait_for_post_comfy_memory(60 * GIB, job_id=job_id)
        request = Request(f"{COMFY_API}/prompt", data=json.dumps({"prompt":graph}).encode(), headers={"Content-Type":"application/json"}, method="POST")
        with urlopen(request, timeout=30) as response:
            prompt_id = json.loads(response.read())["prompt_id"]
        if job_id:
            _update_image_job(job_id, status="processing", stage="qwen_repairing", qwen_prompt_id=prompt_id, heartbeat_at=_iso_now())
        deadline = time.time() + 1800
        while time.time() < deadline:
            time.sleep(2)
            if job_id:
                current_job = _load_image_jobs().get("jobs", {}).get(job_id, {})
                if current_job.get("status") == "failed":
                    _cancel_comfy_prompt(prompt_id)
                    raise RuntimeError(str(current_job.get("error") or "图片任务已停止"))
                _update_image_job(job_id, heartbeat_at=_iso_now(), stage="qwen_repairing")
            with urlopen(f"{COMFY_API}/history/{prompt_id}", timeout=30) as response:
                history = json.loads(response.read())
            if prompt_id not in history:
                continue
            record = history[prompt_id]
            if record.get("status", {}).get("status_str") != "success":
                raise RuntimeError(f"Qwen-Edit 独立修复失败：{str(record.get('status', {}).get('messages', []))[-500:]}")
            output = record["outputs"]["15"]["images"][0]
            shutil.copy2(COMFY_OUTPUT / output.get("subfolder", "") / output["filename"], target)
            return {
                "generation_workflow":"FLUX.1 Schnell GGUF Q8_0",
                "repair_workflow":"Qwen Image Edit 2511",
                "workflow_mode":"sequential_independent",
                "repair_source":str(source),
                "schnell_prompt_id":str(_load_image_jobs().get("jobs", {}).get(job_id, {}).get("schnell_prompt_id", "")) if job_id else "",
                "qwen_prompt_id":prompt_id,
                "repair_mode":"masked_local_inpaint",
                "width":width,
                "height":height,
            }
        raise RuntimeError("Qwen-Edit 独立修复超时")
    finally:
        if 'prompt_id' in locals():
            _cancel_comfy_prompt(prompt_id)
        _free_comfy_memory()
        input_path.unlink(missing_ok=True)
        mask_path.unlink(missing_ok=True)



def _reference_path(url: str) -> Path:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    filename = unquote(query.get("filename", [""])[0]).lstrip("/")
    subfolder = unquote(query.get("subfolder", [""])[0]).strip("/")
    relative = Path(subfolder) / filename if subfolder and "/" not in filename else Path(filename)
    target = (OUTPUT_ROOT / relative).resolve()
    if OUTPUT_ROOT not in target.parents or not target.is_file(): raise RuntimeError("人物参考图不存在")
    return target


def _generate_qwen_character_variant(
    name: object,
    prompt: object,
    width: object,
    height: object,
    identity_reference_url: str,
    clothing_reference_url: str,
    target_pose: str,
    character_sheet_urls: list[str] | None = None,
    *,
    job_id: str | None = None,
) -> dict:
    """Generate one fixed character view with ComfyUI's official angle LoRA."""
    pose_prompts = {
        "front_full": "Keep the camera at an exact zero-degree full-body front view, facing the viewer.",
        "left_45_full": "Turn the same person only 35 degrees from the front toward the person's left, producing a left three-quarter view that measures 30 to 60 degrees. Both eyes, the far cheek and part of both sides of the torso must remain visible. This must not become a 90-degree side profile and must never mirror into a right view.",
        "right_45_full": "Turn the same person only 35 degrees from the front toward the person's right, producing a right three-quarter view that measures 30 to 60 degrees. Both eyes, the far cheek and part of both sides of the torso must remain visible. This must not become a 90-degree side profile and must never mirror into a left view.",
        "side_90_full": "Rotate the camera exactly 90 degrees to the right into a strict full-body side profile.",
        "back_full": "Rotate the camera exactly 180 degrees into a strict full-body rear view; the face must be completely invisible.",
        "front_half": "Create a close-up half-body portrait at exact zero-degree front eye level. Center the person; crop at the waist; keep hands fully out of frame; keep a tiny margin above the complete head. The head-to-waist subject occupies about 75 percent of image height, with both shoulders clear of the side edges and balanced side margins.",
    }
    if target_pose not in pose_prompts:
        raise RuntimeError(f"Qwen多角度不支持的目标角度：{target_pose}")
    if target_pose != "front_half":
        pose_prompts[target_pose] += " Keep clear background above the highest hair point at no less than 8 percent of image height and below the lowest shoe sole at no less than 3 percent; these are minimum margins, not fixed targets."
    angle_lora_weight = 0.35 if target_pose in {"left_45_full", "right_45_full"} else 1.0
    # Qwen variants are serialized by the shared image resource claim, but
    # ComfyUI releases the previous model asynchronously.  Use the same
    # bounded/cancellable release handshake as the other image providers so a
    # serial batch cannot mistake the preceding Qwen allocation for a second
    # concurrent workload.
    _wait_for_post_comfy_memory(60 * GIB, job_id=job_id)
    identity_source = _reference_path(identity_reference_url)
    try:
        clothing_source = _reference_path(clothing_reference_url)
    except Exception:
        clothing_source = identity_source
        clothing_reference_url = identity_reference_url
    COMFY_INPUT.mkdir(parents=True, exist_ok=True)
    identity_name = f"short_drama_qwen_angles/{uuid4().hex}_identity.png"
    clothing_name = f"short_drama_qwen_angles/{uuid4().hex}_clothing.png"
    identity_input = COMFY_INPUT / identity_name
    clothing_input = COMFY_INPUT / clothing_name
    sheet_name = f"short_drama_qwen_angles/{uuid4().hex}_character_sheet.png"
    sheet_input = COMFY_INPUT / sheet_name
    identity_input.parent.mkdir(parents=True, exist_ok=True)
    sheet_sources: list[Path] = []
    try:
        shutil.copy2(identity_source, identity_input)
        shutil.copy2(clothing_source, clothing_input)
        for url in character_sheet_urls or []:
            try:
                source = _reference_path(url)
            except Exception:
                continue
            if source not in {identity_source, clothing_source} and source not in sheet_sources:
                sheet_sources.append(source)
        if sheet_sources:
            sheet_input.parent.mkdir(parents=True, exist_ok=True)
            script = """from PIL import Image,ImageOps;import sys,math
paths=sys.argv[1:-1];out=sys.argv[-1];thumbs=[]
for path in paths:
 im=Image.open(path).convert('RGB');im.thumbnail((360,640),Image.Resampling.LANCZOS);thumbs.append(ImageOps.pad(im,(360,640),color=(128,128,128)))
cols=min(3,len(thumbs));rows=math.ceil(len(thumbs)/cols);sheet=Image.new('RGB',(cols*360,rows*640),(128,128,128))
for index,im in enumerate(thumbs):sheet.paste(im,((index%cols)*360,(index//cols)*640))
sheet.save(out)
"""
            subprocess.run([str(COMFY_PYTHON), "-c", script, *[str(path) for path in sheet_sources], str(sheet_input)], check=True, capture_output=True, text=True, timeout=120)
        # Keep each command reproducible without turning retries into identical
        # clones. The retry correction is part of `prompt`, so a corrected
        # attempt receives a different deterministic seed while the same exact
        # command remains stable across recovery/replay.
        seed_material = identity_source.read_bytes() + target_pose.encode("utf-8") + str(prompt).encode("utf-8")
        fixed_seed = int(hashlib.sha256(seed_material).hexdigest()[:8], 16)
    except Exception:
        identity_input.unlink(missing_ok=True)
        clothing_input.unlink(missing_ok=True)
        sheet_input.unlink(missing_ok=True)
        _free_comfy_memory()
        raise
    angle_prompt = (
        f"{pose_prompts[target_pose]} Image 1 is the accepted full-body clothing and body-proportion reference. "
        "Image 2 is the accepted face and hairstyle identity reference. Keep exactly the same single Chinese person, "
        "face identity, age, hair color, hairstyle structure, garment color, collar, fabric, embroidery and natural body proportions. "
        + ("Keep the complete top of the hair, both shoulders and the body through the waist inside frame; hands must remain outside the frame. Use a completely plain solid neutral gray background with no objects. No full-body distant framing. The half-body portrait and all three full-body angles jointly lock identity, body, clothing and accessories. " if target_pose == "front_half" else "Keep the complete top of the hair and both complete shoes inside frame with clear margins, on a seamless neutral gray studio background. ")
        + "No text, watermark, logo, props, scenery, extra person, duplicate body or cropped head. "
        "Maintain consistent character identity and costume details across all angles. Refer to Image 3 as the confirmed multi-angle character dossier when present. "
        f"Asset specification: {str(prompt)[:900]}"
    )
    if target_pose == "side_90_full":
        angle_prompt += " Only one eye and one side of the nose may be visible; far-side shoulder, arm, hip, leg and shoe must be occluded. No front or three-quarter view."
    graph = {
        "1":{"class_type":"LoadImage","inputs":{"image":clothing_name}},
        "2":{"class_type":"ImageScale","inputs":{"image":["1",0],"upscale_method":"lanczos","width":928,"height":1664,"crop":"disabled"}},
        "3":{"class_type":"FluxKontextImageScale","inputs":{"image":["2",0]}},
        "4":{"class_type":"LoadImage","inputs":{"image":identity_name}},
        "5":{"class_type":"ImageScale","inputs":{"image":["4",0],"upscale_method":"lanczos","width":928,"height":1664,"crop":"disabled"}},
        "6":{"class_type":"FluxKontextImageScale","inputs":{"image":["5",0]}},
        "7":{"class_type":"UNETLoader","inputs":{"unet_name":"qwen_image_edit_2511_bf16.safetensors","weight_dtype":"default"}},
        "8":{"class_type":"LoraLoaderModelOnly","inputs":{"model":["7",0],"lora_name":"qwen-image-edit-2511-multiple-angles-lora.safetensors","strength_model":angle_lora_weight}},
        "9":{"class_type":"ModelSamplingAuraFlow","inputs":{"model":["8",0],"shift":3.1}},
        "10":{"class_type":"CFGNorm","inputs":{"model":["9",0],"strength":1.0}},
        "11":{"class_type":"LoraLoaderModelOnly","inputs":{"model":["10",0],"lora_name":"Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors","strength_model":1.0}},
        "12":{"class_type":"CLIPLoader","inputs":{"clip_name":"qwen_2.5_vl_7b_fp8_scaled.safetensors","type":"qwen_image","device":"default"}},
        "13":{"class_type":"VAELoader","inputs":{"vae_name":"qwen_image_vae.safetensors"}},
        "14":{"class_type":"TextEncodeQwenImageEditPlus","inputs":{"clip":["12",0],"vae":["13",0],"image1":["3",0],"image2":["6",0],"prompt":angle_prompt}},
        "15":{"class_type":"TextEncodeQwenImageEditPlus","inputs":{"clip":["12",0],"vae":["13",0],"image1":["3",0],"image2":["6",0],"prompt":""}},
        "16":{"class_type":"FluxKontextMultiReferenceLatentMethod","inputs":{"conditioning":["14",0],"reference_latents_method":"index_timestep_zero"}},
        "17":{"class_type":"FluxKontextMultiReferenceLatentMethod","inputs":{"conditioning":["15",0],"reference_latents_method":"index_timestep_zero"}},
        "18":{"class_type":"VAEEncode","inputs":{"pixels":["3",0],"vae":["13",0]}},
        "19":{"class_type":"KSampler","inputs":{"model":["11",0],"seed":int(time.time_ns() % 2**32),"steps":4,"cfg":1.0,"sampler_name":"euler","scheduler":"simple","positive":["16",0],"negative":["17",0],"latent_image":["18",0],"denoise":1.0}},
        "20":{"class_type":"VAEDecode","inputs":{"samples":["19",0],"vae":["13",0]}},
        "21":{"class_type":"SaveImage","inputs":{"images":["20",0],"filename_prefix":f"short_drama/{_safe_name(name)}_qwen_angle"}},
    }
    if sheet_sources:
        graph["22"] = {"class_type":"LoadImage","inputs":{"image":sheet_name}}
        graph["23"] = {"class_type":"ImageScale","inputs":{"image":["22",0],"upscale_method":"lanczos","width":928,"height":1664,"crop":"disabled"}}
        graph["14"]["inputs"]["image3"] = ["23",0]
        graph["15"]["inputs"]["image3"] = ["23",0]
    graph["19"]["inputs"]["seed"] = fixed_seed
    prompt_id = ""
    try:
        request = Request(f"{COMFY_API}/prompt", data=json.dumps({"prompt":graph}).encode(), headers={"Content-Type":"application/json"}, method="POST")
        with urlopen(request, timeout=30) as response:
            prompt_id = json.loads(response.read())["prompt_id"]
        if job_id:
            _update_image_job(job_id, status="processing", stage="qwen_variant", qwen_prompt_id=prompt_id, heartbeat_at=_iso_now())
        deadline = time.time() + 1800
        while time.time() < deadline:
            time.sleep(2)
            if job_id:
                current_job = _load_image_jobs().get("jobs", {}).get(job_id, {})
                if current_job.get("status") == "failed":
                    raise RuntimeError(str(current_job.get("error") or "图片任务已停止"))
                _update_image_job(job_id, heartbeat_at=_iso_now(), stage="qwen_variant")
            with urlopen(f"{COMFY_API}/history/{prompt_id}", timeout=30) as response:
                history = json.loads(response.read())
            if prompt_id not in history:
                continue
            record = history[prompt_id]
            if record.get("status", {}).get("status_str") != "success":
                raise RuntimeError("Qwen人物多角度生成失败")
            output = record["outputs"]["21"]["images"][0]
            generated = COMFY_OUTPUT / output.get("subfolder", "") / output["filename"]
            target = OUTPUT_ROOT / "images" / f"{_safe_name(name)}.png"
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(generated, target)
            return {
                "url":f"/api/result-media?filename={target.name}&subfolder=images", "filename":target.name, "subfolder":"images",
                "workflow_mode":"qwen_2511_multiple_angles", "base_model":"qwen_image_edit_2511_bf16.safetensors",
                "angle_lora":"qwen-image-edit-2511-multiple-angles-lora.safetensors", "angle_lora_weight":angle_lora_weight,
                "acceleration_lora":"Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors", "steps":4, "cfg":1.0,
                "identity_reference_url":identity_reference_url, "clothing_reference_url":clothing_reference_url,
                "target_pose":target_pose, "comfy_prompt_id":prompt_id, "seed":fixed_seed,
                "character_sheet_reference_count":len(sheet_sources),
            }
        raise RuntimeError("Qwen人物多角度生成超时")
    finally:
        if prompt_id:
            _cancel_comfy_prompt(prompt_id)
        identity_input.unlink(missing_ok=True)
        clothing_input.unlink(missing_ok=True)
        sheet_input.unlink(missing_ok=True)
        _free_comfy_memory()


def _latest_completed_asset_image_url(project_id: object, asset_kind: object, asset_subject: object) -> str:
    """Recover the newest existing baseline when persisted UI state points at a deleted retry."""
    subject = str(asset_subject or "").split(":", 1)[0]
    expected = f"{project_id}:{asset_kind}:{subject}"
    jobs = list(_load_image_jobs().get("jobs", {}).values())
    for job in reversed(jobs):
        if job.get("status") != "completed" or str(job.get("subject_key", "")) != expected:
            continue
        image = job.get("image") if isinstance(job.get("image"), dict) else {}
        url = str(image.get("url", ""))
        try:
            _reference_path(url)
        except Exception:
            continue
        return url
    return ""


def _write_character_pose_template(target: Path, pose: str, width: int, height: int) -> Path:
    """Write a deterministic OpenPose-style control image without another model load."""
    canvas = bytearray(width * height * 3)

    def dot(x: int, y: int, radius: int, color: tuple[int, int, int]) -> None:
        for py in range(max(0, y - radius), min(height, y + radius + 1)):
            for px in range(max(0, x - radius), min(width, x + radius + 1)):
                if (px - x) ** 2 + (py - y) ** 2 <= radius ** 2:
                    offset = (py * width + px) * 3
                    canvas[offset:offset + 3] = bytes(color)

    def line(start: tuple[int, int], end: tuple[int, int], color: tuple[int, int, int], thickness: int = 7) -> None:
        x0, y0 = start; x1, y1 = end
        steps = max(abs(x1 - x0), abs(y1 - y0), 1)
        for step in range(steps + 1):
            ratio = step / steps
            dot(round(x0 + (x1 - x0) * ratio), round(y0 + (y1 - y0) * ratio), thickness, color)

    center = width // 2
    back_view = pose == "back_full"
    if pose == "side_90_full":
        nose = (center + width * 4 // 100, height * 12 // 100)
        neck = (center, height * 18 // 100)
        shoulder_left = shoulder_right = (center, height * 22 // 100)
        hip_left = hip_right = (center, height * 48 // 100)
    else:
        nose = (center, height * 15 // 100)
        neck = (center, height * 23 // 100)
        shoulder_left, shoulder_right = (center - width * 11 // 100, height * 26 // 100), (center + width * 11 // 100, height * 26 // 100)
        hip_left, hip_right = (center - width * 6 // 100, height * 47 // 100), (center + width * 6 // 100, height * 47 // 100)
    elbow_left, elbow_right = (shoulder_left[0] - width * 3 // 100, height * 36 // 100), (shoulder_right[0] + width * 3 // 100, height * 36 // 100)
    wrist_left, wrist_right = (elbow_left[0], height * 46 // 100), (elbow_right[0], height * 46 // 100)
    leg_spread = width * (2 if pose == "side_90_full" else 5) // 100
    knee_left, knee_right = (center - leg_spread, height * 68 // 100), (center + leg_spread, height * 68 // 100)
    # Keep the complete feet comfortably inside the control canvas. Placing the
    # toes close to the final pixels repeatedly caused SDXL to crop the shoes.
    ankle_left, ankle_right = (center - leg_spread, height * 89 // 100), (center + leg_spread, height * 89 // 100)
    toe_left, toe_right = (ankle_left[0] - width // 100, height * 93 // 100), (ankle_right[0] + width // 100, height * 93 // 100)
    joints = [neck, shoulder_left, shoulder_right, elbow_left, elbow_right, wrist_left, wrist_right, hip_left, hip_right, knee_left, knee_right, ankle_left, ankle_right, toe_left, toe_right]
    if not back_view: joints.insert(0, nose)
    if pose == "side_90_full":
        # A profile skeleton must expose only the near-side limb chain. Two
        # parallel chains are interpreted by OpenPose ControlNet as a front view.
        joints = [nose, neck, shoulder_right, elbow_right, wrist_right, hip_right, knee_right, ankle_right, toe_right]
        bones = [(nose, neck), (neck, shoulder_right), (shoulder_right, elbow_right), (elbow_right, wrist_right),
                 (neck, hip_right), (hip_right, knee_right), (knee_right, ankle_right), (ankle_right, toe_right)]
    else:
        bones = ([] if back_view else [(nose, neck)]) + [(shoulder_left, shoulder_right), (neck, hip_left), (neck, hip_right), (hip_left, hip_right),
                 (shoulder_left, elbow_left), (elbow_left, wrist_left), (shoulder_right, elbow_right), (elbow_right, wrist_right),
                 (hip_left, knee_left), (knee_left, ankle_left), (ankle_left, toe_left),
                 (hip_right, knee_right), (knee_right, ankle_right), (ankle_right, toe_right)]
    colors = [(255, 0, 0), (255, 85, 0), (255, 170, 0), (255, 255, 0), (170, 255, 0), (85, 255, 0),
              (0, 255, 0), (0, 255, 85), (0, 255, 170), (0, 255, 255), (0, 170, 255), (0, 85, 255), (0, 0, 255)]
    for index, bone in enumerate(bones): line(*bone, colors[index % len(colors)])
    for joint in joints: dot(*joint, 10, (255, 255, 255))
    target.write_bytes(f"P6\n{width} {height}\n255\n".encode() + canvas)
    return target


def _write_character_side_depth_template(target: Path, width: int, height: int) -> Path:
    """Write a fixed seven-head pure-profile depth silhouette."""
    canvas = bytearray(width * height * 3)

    def dot(x: int, y: int, radius: int, value: int) -> None:
        color = bytes((value, value, value))
        for py in range(max(0, y - radius), min(height, y + radius + 1)):
            for px in range(max(0, x - radius), min(width, x + radius + 1)):
                if (px - x) ** 2 + (py - y) ** 2 <= radius ** 2:
                    offset = (py * width + px) * 3
                    canvas[offset:offset + 3] = color

    def line(start: tuple[int, int], end: tuple[int, int], radius: int, value: int) -> None:
        x0, y0 = start; x1, y1 = end
        steps = max(abs(x1 - x0), abs(y1 - y0), 1)
        for step in range(steps + 1):
            ratio = step / steps
            dot(round(x0 + (x1 - x0) * ratio), round(y0 + (y1 - y0) * ratio), radius, value)

    center = width // 2
    head_radius = height * 6 // 100
    dot(center, height * 11 // 100, head_radius, 235)
    dot(center + width * 4 // 100, height * 12 // 100, width * 2 // 100, 240)
    line((center, height * 17 // 100), (center, height * 48 // 100), width * 6 // 100, 205)
    line((center + width * 3 // 100, height * 23 // 100), (center + width * 3 // 100, height * 49 // 100), width * 2 // 100, 225)
    line((center, height * 47 // 100), (center, height * 89 // 100), width * 3 // 100, 210)
    line((center + width // 100, height * 47 // 100), (center + width // 100, height * 89 // 100), width * 3 // 100, 200)
    line((center, height * 91 // 100), (center + width * 7 // 100, height * 94 // 100), width * 3 // 100, 220)
    target.write_bytes(f"P6\n{width} {height}\n255\n".encode() + canvas)
    return target



def _generate_ipadapter_image(name: object, prompt: object, width: object, height: object, reference_url: str, pose_reference_url: str = "", target_pose: str = "", clothing_reference_url: str = "", *, character_gender: str = "", job_id: str | None = None) -> dict:
    width_value = max(512, min(1024, int(width or 768))); height_value = max(512, min(1664, int(height or 1344)))
    _require_memory(32 * GIB)
    source = _reference_path(reference_url); pose_locked = bool(pose_reference_url or target_pose); COMFY_INPUT.mkdir(parents=True, exist_ok=True)
    controls = APPLICATION_ROOT / "plugins/builtin/short_drama/backend/assets/character_controls"
    generated_pose_source: Path | None = None
    generated_depth_source: Path | None = None
    if target_pose:
        pose_source = controls / f"openpose_{target_pose}_7_5.png"
        if not pose_source.is_file(): raise RuntimeError(f"标准OpenPose模板缺失：{target_pose}")
    else:
        pose_source = _reference_path(pose_reference_url) if pose_reference_url else source
    try:
        clothing_source = _reference_path(clothing_reference_url) if clothing_reference_url else source
    except (FileNotFoundError, ValueError, RuntimeError):
        clothing_source = source
        clothing_reference_url = reference_url
    if target_pose in {"side_90_full", "back_full"} and clothing_source == source:
        raise RuntimeError("侧面和背面必须先确认正面全身图，禁止使用近照推断完整服装")
    face_crop_source = OUTPUT_ROOT / "temp" / f"face_ip_{uuid4().hex}.png"
    clothing_crop_source = OUTPUT_ROOT / "temp" / f"clothing_ip_{uuid4().hex}.png"
    face_crop_source.parent.mkdir(parents=True, exist_ok=True)
    _prepare_ipadapter_reference_crops(source, clothing_source, face_crop_source, clothing_crop_source)
    face_mask_source = OUTPUT_ROOT / "temp" / f"face_mask_{uuid4().hex}.pgm"
    clothing_mask_source = OUTPUT_ROOT / "temp" / f"clothing_mask_{uuid4().hex}.pgm"
    _write_ipadapter_attention_masks(face_mask_source, clothing_mask_source, width_value, height_value)
    input_name = f"short_drama_refs/{uuid4().hex}.png"; input_path = COMFY_INPUT / input_name
    input_path.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(face_crop_source, input_path)
    visual_lock = ""
    try:
        lock_request = Request(
            "http://127.0.0.1:11434/api/generate",
            data=json.dumps({
                "model":"llava:latest",
                "prompt":(
                    "Image 1 is the accepted face/hair reference. Image 2 is the accepted full-body clothing reference. "
                    "Describe only the visible immutable character design as compact JSON strings: "
                    '{"face":"age, face shape and key features","hair":"bangs, part, tied or loose state, braid/ponytail, length and color",'
                    '"clothing":"main color, collar, trim, fastener, fabric and decoration level"}. '
                    "Be literal. Do not infer hidden garments, setting, pose, lighting or art style."
                ),
                "images":[base64.b64encode(path.read_bytes()).decode("ascii") for path in (source, clothing_source)],
                "stream":False,"keep_alive":0,"format":"json",
                "options":{"num_ctx":1536,"num_predict":160,"temperature":0,"seed":31},
            }).encode("utf-8"), headers={"Content-Type":"application/json"}, method="POST",
        )
        with urlopen(lock_request, timeout=600) as response:
            lock_payload = json.loads(response.read())
        lock_data = json.loads(str(lock_payload.get("response", "{}")))
        visual_lock = "IMMUTABLE REFERENCE DESIGN: " + "; ".join(
            f"{key}={str(lock_data.get(key, '')).strip()}" for key in ("face", "hair", "clothing") if str(lock_data.get(key, "")).strip()
        ) + ". "
    except Exception:
        visual_lock = ""
    clothing_input_name = f"short_drama_clothing_refs/{uuid4().hex}.png"; clothing_input_path = COMFY_INPUT / clothing_input_name
    clothing_input_path.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(clothing_crop_source, clothing_input_path)
    face_mask_name = f"short_drama_masks/{uuid4().hex}.pgm"; face_mask_path = COMFY_INPUT / face_mask_name
    clothing_mask_name = f"short_drama_masks/{uuid4().hex}.pgm"; clothing_mask_path = COMFY_INPUT / clothing_mask_name
    face_mask_path.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(face_mask_source, face_mask_path); shutil.copy2(clothing_mask_source, clothing_mask_path)
    pose_input_name = f"short_drama_pose_refs/{uuid4().hex}{pose_source.suffix.lower()}"; pose_input_path = COMFY_INPUT / pose_input_name
    pose_input_path.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(pose_source, pose_input_path)
    depth_source = controls / "side_depth_source_7_5.png" if target_pose == "side_90_full" else pose_source
    depth_input_name = f"short_drama_depth_refs/{uuid4().hex}{depth_source.suffix.lower()}"; depth_input_path = COMFY_INPUT / depth_input_name
    depth_input_path.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(depth_source, depth_input_path)
    pose_rules = {
        "front_full": {
            "positive":"严格0度正面全身，standard 7.5 head-to-body ratio, realistic human proportion, normal limb length, natural leg length, anatomically correct；完整发顶必须入框且无需保留顶部空白，完整鞋底最低点下方必须保留约5%画高纯背景。发型和服装严格匹配已确认参考，服装下摆不得遮挡双侧脚踝、双鞋和完整鞋底。",
            "negative":"elongated legs, overly long arms, disproportionate limbs, ultra tall, stretched body, cartoon exaggerated proportion, cropped feet, hidden feet, covered shoes, floor-length dress, ankle-length dress, hair below chest, waist-length hair, floor-length hair, close-up, half body, oversized head, large head, child proportions, chibi, doll body, short body, extra long legs, side view, back view",
            "ip_weight":0.72, "ip_end":0.60, "ip_weight_type":"style transfer precise", "control":1.20, "depth_control":0.0, "clothing_weight":0.18, "clothing_end":0.50, "clothing_weight_type":"style transfer precise", "refine_denoise":0.28, "cfg":6.0,
        },
        "side_90_full": {
            "positive":"strict pure side profile, angle between 88 and 92 degrees pure side view, body completely vertical side view, shoulders perfectly stacked front-back, torso no backward tilt, head torso legs same vertical plane, full body standing upright, parallel to camera plane, standard 7.5 head-to-body ratio, realistic human proportion, normal limb length, natural leg length, anatomically correct. 严格人物档案照右侧视图，远侧肩膀、手臂、髋部、腿和鞋必须被近侧轮廓完全重叠遮挡，禁止露出后背和正面胸口；头部水平，下巴中立，只允许一只眼睛、一侧眉毛和一侧嘴角可见。完整发顶入框且无需顶部空白，完整鞋底下方保留约5%画高纯背景。",
            "negative":"elongated legs, overly long arms, disproportionate limbs, ultra tall, stretched body, cartoon exaggerated proportion, three-quarter view, half side, body leaning backward, shoulder exposed forward or backward, torso rotation, oblique side, front-facing body, rear three-quarter body, back visible, both shoulders visible, both arms separated, both legs separated, front chest visible, front-facing face, three-quarter face, 45 degree face, face turned toward camera, looking at camera, direct gaze, both eyes visible, two eyebrows visible, symmetrical face, front nose, tilted head, chin up, chin down, looking upward, looking downward, back view, cropped feet, feet out of frame, close-up, half body",
            "ip_weight":0.45, "ip_end":0.45, "ip_weight_type":"style transfer precise", "control":1.05, "depth_control":0.55, "clothing_weight":0.72, "clothing_end":0.45, "clothing_weight_type":"style transfer precise", "refine_denoise":0.18, "cfg":5.0,
        },
        "back_full": {
            "positive":"严格180度纯背面全身，人物背对镜头，后脑、后背、后腰、腿后侧和鞋跟可见；脸、眼睛、鼻子、嘴巴和正面胸口必须完全不可见；完整发顶必须入框且无需顶部空白，完整鞋底下方必须保留约5%画高纯背景。",
            "negative":"face visible, eyes visible, front-facing, looking at camera, three-quarter view, side view, chest visible, cropped feet, feet out of frame, close-up, half body, elongated body",
            "ip_weight":0.12, "ip_end":0.20, "ip_weight_type":"style transfer precise", "control":0.90, "depth_control":0.0, "clothing_weight":0.68, "clothing_end":0.50, "clothing_weight_type":"composition precise", "refine_denoise":0.18, "cfg":6.0,
        },
    }
    profile = pose_rules.get(target_pose, {"positive":"", "negative":"", "ip_weight":1.0, "ip_end":1.0, "ip_weight_type":"style transfer precise", "control":0.0, "depth_control":0.0, "clothing_weight":0.68, "clothing_weight_type":"style transfer precise", "cfg":6.0})
    profile.setdefault("depth_control", 0.0)
    profile.setdefault("clothing_end", 0.70)
    profile.setdefault("refine_denoise", 0.24)
    body_ratio = "幼态或少女角色固定约6.5头身，禁止成人超模九头身。" if any(token in str(prompt).lower() for token in ("少女", "幼态", "young girl", "cute girl")) else "使用自然影视人物约7头身比例，禁止九头身、腿部拉长和躯干压缩。"
    conditioned_prompt = f"{visual_lock}{profile['positive']} exact same embroidery pattern, identical fabric color, consistent clothing cut with baseline image. 严格保留基准图实际可见的脸、刘海、分缝、扎发方式、辫子、发长、发色、领口、扣饰、服装主色和简洁程度；禁止改发型、解开发辫、增加印花、撞色面板、发冠、头饰、皇冠、金甲、披风、拖尾、繁复刺绣或礼服。完整发顶上方纯背景留白不得少于画高8%，完整鞋底下方纯背景留白不得少于画高3%；两者都是最低值而非固定值。无缝平整纯色哑光中性灰摄影棚背景，禁止纹理、斑驳、渐变、阴影墙、建筑、家具、花木、景深或环境布景。{body_ratio}{prompt or 'cinematic portrait'}"
    negative_prompt = (
        "different person, changed identity, changed face shape, changed facial features, different hairstyle, changed hairline, changed hair color, "
        "changed clothes, changed embroidery, altered color, modified clothing style, extra decorations, crown, headdress, hair ornament, gold armor, ornate ceremonial robe, cape, train, heavy embroidery, exposed shoulders, bare shoulders, sleeveless, low neckline, cleavage, underwear, modern dress, modern shoes, "
        "scenery, landscape, environmental background, textured background, mottled background, gradient background, furniture, props, tree, branch, flower, plant, dragon, animal, statue, pedestal, "
        "architecture, mountain, water, weapon, multiple people, duplicate person, bad anatomy, malformed hands, deformed feet, blur, text, watermark, "
        f"{profile['negative']}"
    )
    openpose_control_image = ["11", 0]
    graph = {
        "1":{"class_type":"CheckpointLoaderSimple","inputs":{"ckpt_name":"RealVisXL_V5.0_fp16.safetensors"}},
        "2":{"class_type":"LoadImage","inputs":{"image":input_name}},
        "3":{"class_type":"IPAdapterUnifiedLoaderFaceID","inputs":{"model":["1",0],"preset":"FACEID PLUS V2","lora_strength":0.55,"provider":"CPU"}},
        "4":{"class_type":"IPAdapterFaceID","inputs":{"model":["3",0],"ipadapter":["3",1],"image":["2",0],"attn_mask":["24",0],"weight":profile["ip_weight"],"weight_faceidv2":1.0,"weight_type":profile["ip_weight_type"],"combine_embeds":"average","start_at":0.0,"end_at":profile["ip_end"],"embeds_scaling":"K+V w/ C penalty"}},
        "5":{"class_type":"CLIPTextEncode","inputs":{"clip":["1",1],"text":f"realistic cinematic character reference photography, natural skin texture, traditional Chinese costume matching the accepted reference, both shoes fully visible, {conditioned_prompt}"}},
        "6":{"class_type":"CLIPTextEncode","inputs":{"clip":["1",1],"text":negative_prompt}},
        "7":{"class_type":"EmptyLatentImage","inputs":{"width":width_value,"height":height_value,"batch_size":1}},
        "8":{"class_type":"KSampler","inputs":{"model":["1",0],"seed":int(time.time_ns() % 2**32),"steps":24,"cfg":profile["cfg"],"sampler_name":"dpmpp_2m","scheduler":"karras","positive":["21",0],"negative":["21",1],"latent_image":["7",0],"denoise":1.0}},
        "9":{"class_type":"VAEDecode","inputs":{"samples":["8",0],"vae":["1",2]}},
        "10":{"class_type":"SaveImage","inputs":{"images":["22",0] if target_pose == "front_full" else ["28",0],"filename_prefix":f"short_drama/{_safe_name(name)}"}},
        "11":{"class_type":"LoadImage","inputs":{"image":pose_input_name}},
        "12":{"class_type":"OpenposePreprocessor","inputs":{"image":["11",0],"detect_hand":"enable","detect_body":"enable","detect_face":"enable","resolution":768,"scale_stick_for_xinsr_cn":"enable"}},
        "13":{"class_type":"ControlNetLoader","inputs":{"control_net_name":"openpose-sdxl-1.0.safetensors"}},
        "14":{"class_type":"ControlNetApplyAdvanced","inputs":{"positive":["5",0],"negative":["6",0],"control_net":["13",0],"image":openpose_control_image,"strength":profile["control"] if pose_locked else 0.0,"start_percent":0.0,"end_percent":0.95,"vae":["1",2]}},
        "15":{"class_type":"LoadImage","inputs":{"image":clothing_input_name}},
        "16":{"class_type":"IPAdapterModelLoader","inputs":{"ipadapter_file":"ip-adapter-plus_sdxl_vit-h.safetensors"}},
        "17":{"class_type":"CLIPVisionLoader","inputs":{"clip_name":"CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors"}},
        "18":{"class_type":"IPAdapterAdvanced","inputs":{"model":["4",0],"ipadapter":["16",0],"image":["15",0],"attn_mask":["25",0],"clip_vision":["17",0],"weight":profile["clothing_weight"],"weight_type":profile["clothing_weight_type"],"combine_embeds":"average","start_at":0.0,"end_at":profile["clothing_end"],"embeds_scaling":"K+V w/ C penalty"}},
        "19":{"class_type":"DepthAnythingV2Preprocessor","inputs":{"image":["23",0],"ckpt_name":"depth_anything_v2_vitl.pth","resolution":768}},
        "20":{"class_type":"ControlNetLoader","inputs":{"control_net_name":"xinsir-controlnet-depth-sdxl-1.0.safetensors"}},
        "21":{"class_type":"ControlNetApplyAdvanced","inputs":{"positive":["14",0],"negative":["14",1],"control_net":["20",0],"image":["19",0],"strength":profile["depth_control"] if target_pose == "side_90_full" else 0.0,"start_percent":0.0,"end_percent":0.90,"vae":["1",2]}},
        "23":{"class_type":"LoadImage","inputs":{"image":depth_input_name}},
        "24":{"class_type":"LoadImageMask","inputs":{"image":face_mask_name,"channel":"red"}},
        "25":{"class_type":"LoadImageMask","inputs":{"image":clothing_mask_name,"channel":"red"}},
        "26":{"class_type":"VAEEncode","inputs":{"pixels":["9",0],"vae":["1",2]}},
        "27":{"class_type":"KSampler","inputs":{"model":["18",0],"seed":int((time.time_ns() + 1) % 2**32),"steps":12,"cfg":4.0,"sampler_name":"dpmpp_2m","scheduler":"karras","positive":["5",0],"negative":["6",0],"latent_image":["26",0],"denoise":profile["refine_denoise"]}},
        "28":{"class_type":"VAEDecode","inputs":{"samples":["27",0],"vae":["1",2]}},
    }
    if target_pose == "front_full":
        graph["22"] = {
            "class_type":"ReActorFaceSwap",
            "inputs":{
                "enabled":True,
                "input_image":["28",0],
                "source_image":["2",0],
                "swap_model":"inswapper_128.onnx",
                "facedetection":"retinaface_resnet50",
                "face_restore_model":"none",
                "face_restore_visibility":1.0,
                "codeformer_weight":0.5,
                "detect_gender_input":character_gender if character_gender in {"female", "male"} else "no",
                "detect_gender_source":character_gender if character_gender in {"female", "male"} else "no",
                "input_faces_index":"0",
                "source_faces_index":"0",
                "console_log_level":1,
            },
        }
    prompt_id = ""
    try:
        request = Request(f"{COMFY_API}/prompt", data=json.dumps({"prompt":graph}).encode(), headers={"Content-Type":"application/json"}, method="POST")
        with urlopen(request, timeout=30) as response: prompt_id = json.loads(response.read())["prompt_id"]
        if job_id:
            _update_image_job(job_id, status="processing", stage="ipadapter_openpose", comfy_prompt_id=prompt_id, heartbeat_at=_iso_now())
        deadline = time.time() + 900
        while time.time() < deadline:
            time.sleep(2)
            if job_id:
                current_job = _load_image_jobs().get("jobs", {}).get(job_id, {})
                if current_job.get("status") == "failed":
                    _cancel_comfy_prompt(prompt_id)
                    raise RuntimeError(str(current_job.get("error") or "图片任务已停止"))
                _update_image_job(job_id, heartbeat_at=_iso_now(), stage="ipadapter_openpose")
            with urlopen(f"{COMFY_API}/history/{prompt_id}", timeout=30) as response: history = json.loads(response.read())
            if prompt_id not in history: continue
            record = history[prompt_id]
            if record.get("status", {}).get("status_str") != "success": raise RuntimeError("IP-Adapter 人物一致性生图失败")
            image = record["outputs"]["10"]["images"][0]; generated = COMFY_OUTPUT / image.get("subfolder", "") / image["filename"]
            target = OUTPUT_ROOT / "images" / f"{_safe_name(name)}.png"; target.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(generated, target)
            return {"url":f"/api/result-media?filename={target.name}&subfolder=images","filename":target.name,"subfolder":"images","workflow_mode":"two_stage_pose_then_identity_clothing","base_model":"RealVisXL_V5.0_fp16.safetensors","style_lora":"none","style_lora_weight":0.0,"character_lora":"none","character_lora_weight":0.0,"identity_model":"IP-Adapter FaceID Plus V2 SDXL","identity_weight":profile["ip_weight"],"identity_end":profile["ip_end"],"clothing_model":"Regional IP-Adapter Plus SDXL ViT-H","clothing_weight":profile["clothing_weight"],"clothing_reference_url":clothing_reference_url or reference_url,"pose_model":"OpenPose ControlNet SDXL + Depth ControlNet SDXL","pose_weight":profile["control"],"depth_weight":profile["depth_control"],"identity_clothing_denoise":profile["refine_denoise"],"target_pose":target_pose,"width":width_value,"height":height_value,"comfy_prompt_id":prompt_id}
        raise RuntimeError("IP-Adapter 人物一致性生图超时")
    finally:
        if prompt_id:
            _cancel_comfy_prompt(prompt_id)
        input_path.unlink(missing_ok=True); clothing_input_path.unlink(missing_ok=True); pose_input_path.unlink(missing_ok=True); depth_input_path.unlink(missing_ok=True)
        face_mask_path.unlink(missing_ok=True); clothing_mask_path.unlink(missing_ok=True)
        face_crop_source.unlink(missing_ok=True); clothing_crop_source.unlink(missing_ok=True); face_mask_source.unlink(missing_ok=True); clothing_mask_source.unlink(missing_ok=True)
        if generated_pose_source: generated_pose_source.unlink(missing_ok=True)
        if generated_depth_source: generated_depth_source.unlink(missing_ok=True)
        _free_comfy_memory()


def _extract_openpose(name: object, reference_url: str) -> dict:
    source = _reference_path(reference_url); COMFY_INPUT.mkdir(parents=True, exist_ok=True)
    input_name = f"short_drama_pose_input/{uuid4().hex}{source.suffix.lower()}"; input_path = COMFY_INPUT / input_name
    input_path.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(source, input_path)
    graph = {
        "1":{"class_type":"LoadImage","inputs":{"image":input_name}},
        "2":{"class_type":"OpenposePreprocessor","inputs":{"image":["1",0],"detect_hand":"enable","detect_body":"enable","detect_face":"enable","resolution":768,"scale_stick_for_xinsr_cn":"enable"}},
        "3":{"class_type":"SaveImage","inputs":{"images":["2",0],"filename_prefix":f"short_drama_pose/{_safe_name(name)}"}},
    }
    request = Request(f"{COMFY_API}/prompt", data=json.dumps({"prompt":graph}).encode(), headers={"Content-Type":"application/json"}, method="POST")
    with urlopen(request, timeout=30) as response: prompt_id = json.loads(response.read())["prompt_id"]
    deadline = time.time() + 600
    while time.time() < deadline:
        time.sleep(1)
        with urlopen(f"{COMFY_API}/history/{prompt_id}", timeout=30) as response: history = json.loads(response.read())
        if prompt_id not in history: continue
        record = history[prompt_id]
        if record.get("status", {}).get("status_str") != "success": raise RuntimeError("OpenPose 骨骼提取失败")
        image = record["outputs"]["3"]["images"][0]; generated = COMFY_OUTPUT / image.get("subfolder", "") / image["filename"]
        target = OUTPUT_ROOT / "poses" / f"{_safe_name(name)}.png"; target.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(generated, target)
        input_path.unlink(missing_ok=True); _free_comfy_memory()
        return {"url":f"/api/result-media?filename={target.name}&subfolder=poses","filename":target.name,"subfolder":"poses","model":"OpenPose body+hand+face"}
    raise RuntimeError("OpenPose 骨骼提取超时")


def _generate_video_capability(job_id: str, body: dict) -> dict:
    _generate_video_job(job_id, body)
    return {"job_id":job_id, "status":str(_load_video_jobs().get("jobs", {}).get(job_id, {}).get("status") or "failed")}


def _generate_tts_capability(body: dict) -> dict:
    text = str(body.get("text", "")).strip()
    if not text:
        raise ValueError("配音文本不能为空")
    episode = max(1, int(body.get("episode", 1))); shot = max(1, int(body.get("shot_number", 1)))
    target = OUTPUT_ROOT / "audio" / f"episode_{episode}_shot_{shot}.flac"
    with _claim_production_resource("audio", f"tts-{episode}-{shot}-{uuid4()}", timeout=1800):
        _require_memory(16 * GIB)
        instruction = f"{body.get('emotion_instruction', '自然、清晰、有情绪的中文短剧配音')}。必须执行：{_production_spec_for('audio')}"
        _run_comfy_function("tts", [text, str(body.get("speaker", "Serena")), instruction], target, f"short_drama/episode_{episode}_shot_{shot}_voice")
    return {"audio":{"url":f"/api/result-media?filename={target.name}&subfolder=audio", "path":str(target), "duration":_media_duration(target), "model":"Qwen3-TTS-0.6B"}}


def _generate_lipsync_capability(body: dict, engine: str) -> dict:
    episode = max(1, int(body.get("episode", 1))); shot = max(1, int(body.get("shot_number", 1)))
    suffix = "musetalk" if engine == "musetalk" else "latentsync"
    target = OUTPUT_ROOT / "videos" / f"episode_{episode}_shot_{shot}_{suffix}.mp4"
    video = _resolve_media_input(body.get("video_url")); audio = _resolve_media_input(body.get("audio_url"))
    with _claim_production_resource("video", f"lipsync-{episode}-{shot}-{uuid4()}", timeout=VIDEO_QUEUE_TIMEOUT_SECONDS):
        _require_memory(24 * GIB if engine == "musetalk" else 40 * GIB)
        raw_target = OUTPUT_ROOT / "videos" / f"episode_{episode}_shot_{shot}_{suffix}_raw.mp4"
        if engine == "musetalk":
            _run_comfy_function("musetalk", [video, audio], raw_target, f"short_drama/episode_{episode}_shot_{shot}_musetalk")
        else:
            _run_latentsync(video, audio, raw_target, int(body.get("inference_steps", 20)))
        _attach_dialogue_audio(raw_target, audio, target)
    return {"video_url":f"/api/result-media?filename={target.name}&subfolder=videos", "path":str(target), "model":"MuseTalk" if engine == "musetalk" else "LatentSync-1.6"}


def _audio_repair_capability(body: dict) -> dict:
    video = _resolve_media_input(body.get("video_url")); audio = _resolve_media_input(body.get("audio_url")); target = OUTPUT_ROOT / "videos" / f"audio_repair_{uuid4().hex[:12]}.mp4"
    subprocess.run([str(FFMPEG), "-y", "-i", str(video), "-i", str(audio), "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-shortest", str(target)], check=True, capture_output=True, text=True, timeout=600)
    return {"video_url": f"/api/result-media?filename={target.name}&subfolder=videos", "path": str(target)}


def _composition_capability(body: dict) -> dict:
    episode = max(1, int(body.get("episode", 1))); videos = body.get("videos", [])
    for item in videos:
        if item.get("has_dialogue") and not item.get("voice_ready"): raise ValueError(f"镜头{item.get('shot_number', '')}配音尚未完成")
        if item.get("has_dialogue") and not item.get("lip_sync_ready"): raise ValueError(f"镜头{item.get('shot_number', '')}口型同步尚未完成")
        if item.get("has_dialogue") and not item.get("subtitle_ready"): raise ValueError(f"镜头{item.get('shot_number', '')}字幕尚未完成")
    subtitles = body.get("subtitles", [])
    if any(not str(item.get("text", "")).strip() or float(item.get("end", 0)) <= float(item.get("start", 0)) for item in subtitles): raise ValueError("字幕文本或时间轴尚未完成")
    sources = [_resolve_media_input(item.get("url")) for item in videos]
    if not sources: raise ValueError("没有可合并的分镜视频")
    target_dir = OUTPUT_ROOT / "merged"; clean = target_dir / f"episode_{episode}_clean.mp4"; bgm = target_dir / f"episode_{episode}_bgm.m4a"; mixed = target_dir / f"episode_{episode}_mixed.mp4"; target = target_dir / f"episode_{episode}_master.mp4"
    target_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="short-drama-merge-") as temporary:
        normalized: list[Path] = []
        for index, (item, source) in enumerate(zip(videos, sources, strict=True), 1):
            dialogue_audio = _resolve_media_input(item.get("audio_url")) if item.get("audio_url") else None
            normalized_target = Path(temporary) / f"shot_{index:04d}.mp4"; _normalize_shot_media(source, dialogue_audio, normalized_target); normalized.append(normalized_target)
        concat = Path(temporary) / "concat.txt"
        concat.write_text("\n".join(f"file '{str(path).replace(chr(39), chr(39) + chr(92) + chr(39) + chr(39))}'" for path in normalized), encoding="utf-8")
        _run_ffmpeg(["-f", "concat", "-safe", "0", "-i", str(concat), "-c:v", "copy", "-c:a", "aac", "-ar", "48000", "-b:a", "192k"], clean)
    _invoke_production_capability("audio.bgm", duration=_media_duration(clean), target=bgm); _mix_bgm(clean, bgm, mixed, float(body.get("bgm_volume", 0.18))); _burn_subtitles(mixed, subtitles, target)
    return {"video_url":_media_url(target), "path":str(target), "clean_path":str(mixed), "raw_clean_path":str(clean), "bgm_url":_media_url(bgm), "bgm_path":str(bgm), "bgm_volume":max(0.0, min(1.0, float(body.get("bgm_volume", 0.18)))), "production_evidence":"ffmpeg-concat-bgm-mix-subtitle-v2"}


def _subtitle_reburn_capability(body: dict) -> dict:
    episode = max(1, int(body.get("episode", 1))); source = _resolve_media_input(body.get("clean_path")); target = OUTPUT_ROOT / "merged" / f"episode_{episode}_master.mp4"
    _burn_subtitles(source, body.get("subtitles", []), target)
    return {"video_url":_media_url(target), "path":str(target), "clean_path":str(source)}


def _upscale_capability(body: dict, kind: str) -> dict:
    if kind == "video":
        episode = max(1, int(body.get("episode", 1))); source = _resolve_media_input(body.get("path")); target = OUTPUT_ROOT / "enhanced" / f"episode_{episode}_enhanced.mp4"
        with _claim_production_resource("upscale", f"video-upscale-{episode}-{uuid4()}", timeout=VIDEO_QUEUE_TIMEOUT_SECONDS):
            _require_memory(24 * GIB); _run_comfy_function("video_upscale_interpolate", [source, str(int(body.get("fps", 30)))], target, f"short_drama/episode_{episode}_realesrgan_rife")
        return {"video_url":_media_url(target), "path":str(target), "production_evidence":"ComfyUI RealESRGAN x4 + RIFE 4.9 interpolation 720x1280@30-v1"}
    source = _resolve_media_input(body.get("path") or body.get("image_url")); target = OUTPUT_ROOT / "enhanced" / "images" / f"{_safe_name(body.get('name') or source.stem)}_1080p.png"
    with _claim_production_resource("upscale", f"image-upscale-{uuid4()}", timeout=IMAGE_QUEUE_TIMEOUT_SECONDS):
        _require_memory(16 * GIB); _run_comfy_function("image_upscale", [source], target, f"short_drama/images/{_safe_name(target.stem)}")
    return {"image_url":_media_url(target), "path":str(target), "production_evidence":"ComfyUI RealESRGAN x4 1080x1920-v1"}


def _export_capability(body: dict) -> dict:
    export_id = uuid4().hex[:12]; target_dir = OUTPUT_ROOT / "exports" / export_id; target_dir.mkdir(parents=True, exist_ok=False); files = []
    for item in body.get("items", []):
        source = _resolve_media_input(item.get("path")); filename = f"episode_{int(item.get('episode', 0)):02d}_{body.get('source_version', 'base')}{source.suffix}"; target = target_dir / filename; shutil.copy2(source, target)
        files.append({"episode":item.get("episode"), "filename":filename, "url":_media_url(target), "size":target.stat().st_size, "source_version":body.get("source_version"), "content_fingerprint":item.get("content_fingerprint"), "audit_batch_id":item.get("audit_batch_id"), "production_evidence":item.get("production_evidence"), "audit_evidence":item.get("audit_evidence")})
    manifest = target_dir / "manifest.json"; atomic_write_json(manifest, {"export_id":export_id, "created_at":datetime.now(UTC).isoformat(), "project_name":body.get("project_name"), "mode":body.get("mode"), "source_version":body.get("source_version"), "production_parameters":body.get("production_parameters"), "audit_results":body.get("audit_results"), "files":files})
    return {"files":files, "manifest_url":_media_url(manifest)}


def _identity_refine_capability(body: dict) -> dict:
    source = _resolve_media_input(body.get("image_url")); face = _resolve_media_input(body.get("face_reference_url")); mode = str(body.get("mode") or "pulid").lower()
    if mode not in {"pulid", "reactor"}: raise ValueError("身份修正模式仅支持 pulid 或 reactor")
    target = OUTPUT_ROOT / "enhanced" / "images" / f"{_safe_name(body.get('name') or source.stem)}_{mode}.png"; target.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(source, target)
    with _claim_production_resource("image", f"identity-refine-{uuid4()}", timeout=IMAGE_QUEUE_TIMEOUT_SECONDS):
        _require_memory(24 * GIB if mode == "pulid" else 12 * GIB)
        if mode == "pulid": _pulid_identity_refine(source, face, target, f"short_drama/identity/{_safe_name(target.stem)}")
        else: _apply_storyboard_face_lock(target, face, target.stem)
    return {"image_url":_media_url(target), "path":str(target), "mode":mode, "production_evidence":f"ComfyUI {mode} optional identity refinement-v1"}


def _subtitle_text_audit_capability(body: dict) -> dict:
    errors = []
    for index, item in enumerate(body.get("subtitles", []), 1):
        if not str(item.get("text", "")).strip() or float(item.get("end", 0)) <= float(item.get("start", 0)): errors.append({"subtitle_index":item.get("index", index), "message":"字幕文本或时间轴无效", "suggestion":str(item.get("text", "")).strip()})
    return {"status":"pass" if not errors else "failed", "errors":errors, "evidence":{"validator":"subtitle-timeline-v1", "checked":len(body.get("subtitles", []))}}


def _final_audit_capability(body: dict) -> dict:
    issues = []
    try:
        if _media_duration(_resolve_media_input(body.get("path"))) <= 0: issues.append("成片时长无效")
    except Exception as error: issues.append(str(error))
    if body.get("ocr_status") == "needs_fix": issues.append("字幕 OCR 未通过")
    if body.get("content_compliance_status") != "pass": issues.append("内容合规审核缺少真实通过证据")
    failed = [item for item in body.get("process_audits", []) if any(value not in {"pass", "not_applicable", "baseline_pending_human_confirmation", None} for key, value in item.items() if key != "shot_number")]
    if failed: issues.append("分镜过程审核证据未通过")
    return {"status":"needs_fix" if issues else "pass", "issues":issues, "evidence":{"validator":"final-evidence-gate-v1", "process_audits":len(body.get("process_audits", []))}}


def _import_media_audit_capability(body: dict) -> dict:
    resource = next(item for item in _load_resources().get("resources", []) if item.get("id") == body.get("resource_id")); source = OUTPUT_ROOT / str(resource["subfolder"]) / str(resource["filename"]); duration = _media_duration(source); maximum = float(body.get("max_duration_seconds", 0) or 0)
    if maximum and duration > maximum: raise ValueError(f"媒体时长 {duration:.1f} 秒超过上限 {maximum:.1f} 秒")
    return {"path":str(source), "video_url":_media_url(source), "production_evidence":"user-import-validated-v1"}


def _install_builtin_production_capabilities() -> None:
    global BUILTIN_PRODUCTION_CAPABILITIES_INSTALLED
    with PRODUCTION_CAPABILITIES_INSTALL_LOCK:
        if BUILTIN_PRODUCTION_CAPABILITIES_INSTALLED:
            return
        registrations = (
            ("image.generate", "mlx-flux2-klein", _generate_image),
            ("image.baseline.schnell", "comfy-flux1-schnell-q8", _generate_flux1_schnell_baseline),
            ("image.baseline.klein9b", "mlx-flux2-klein9b", _generate_klein9b_asset_baseline),
            ("image.variant.qwen", "comfy-qwen-image-edit-2511", _generate_qwen_character_variant),
            ("image.variant.ipadapter", "comfy-realvisxl-ipadapter", _generate_ipadapter_image),
            ("image.shot.multireference", "comfy-multireference", _generate_multireference_shot),
            ("pose.extract", "comfy-openpose", _extract_openpose),
            ("asset.3d", "triposr-blender", _generate_asset_3d),
            ("audio.bgm", "ffmpeg-local", _generate_bgm),
            ("video.shot", "comfy-video-router", _generate_video_capability),
            ("video.shot.h3_ref2va", "comfy-minimax-h3-ref2va", _generate_h3_rv2v_video),
            ("audio.tts", "comfy-qwen3-tts", _generate_tts_capability),
            ("video.lipsync", "comfy-musetalk", lambda body: _generate_lipsync_capability(body, "musetalk")),
            ("video.lipsync.fallback", "latentsync-1.6", lambda body: _generate_lipsync_capability(body, "latentsync")),
            ("audio.repair", "ffmpeg-local", _audio_repair_capability),
            ("composition.merge", "ffmpeg-local", _composition_capability),
            ("subtitle.reburn", "ffmpeg-local", _subtitle_reburn_capability),
            ("video.upscale", "comfy-realesrgan-rife", lambda body: _upscale_capability(body, "video")),
            ("image.upscale", "comfy-realesrgan", lambda body: _upscale_capability(body, "image")),
            ("image.identity_refine", "comfy-pulid-reactor", _identity_refine_capability),
            ("export.package", "local-object-store", _export_capability),
            ("audit.subtitle.text", "deterministic-timeline-validator", _subtitle_text_audit_capability),
            ("audit.video.final", "deterministic-evidence-gate", _final_audit_capability),
            ("audit.media.import", "deterministic-media-validator", _import_media_audit_capability),
            ("text.generate.json", "ollama-qwen3-vl-32b", _ollama_json_local),
            ("audit.narrative", "ollama-qwen25-72b", _narrative_audit),
            ("text.narrative.repair", "ollama-qwen25-72b", _narrative_repair),
            ("web.search", "search-provider-router", search_web),
        )
        for capability, provider_id, handler in registrations:
            if not PRODUCTION_CAPABILITIES.has(capability, provider_id):
                PRODUCTION_CAPABILITIES.register(capability, provider_id, handler, metadata={"builtin": True})
            elif PRODUCTION_CAPABILITIES.get(capability, provider_id).metadata.get("builtin"):
                PRODUCTION_CAPABILITIES.register(capability, provider_id, handler, metadata={"builtin": True}, replace_provider=True)
        BUILTIN_PRODUCTION_CAPABILITIES_INSTALLED = True


def _invoke_production_capability(capability: str, **inputs: object):
    _install_builtin_production_capabilities()
    return PRODUCTION_CAPABILITIES.invoke(capability, **inputs)


def _ollama_json(
    prompt: str,
    model: str = TEXT_LIGHT_MODEL,
    estimated_memory: int = TEXT_LIGHT_ESTIMATED_MEMORY,
    *,
    release_model: bool = True,
    keep_alive: int = 0,
    timeout_seconds: int = 600,
    owner_job_id: str = "",
    num_ctx: int = 8192,
    num_predict: int = 2048,
) -> dict:
    return _invoke_production_capability(
        "text.generate.json", prompt=prompt, model=model, estimated_memory=estimated_memory,
        release_model=release_model, keep_alive=keep_alive, timeout_seconds=timeout_seconds, owner_job_id=owner_job_id, num_ctx=num_ctx, num_predict=num_predict,
    )


def _unavailable_audit(capability: str) -> dict:
    return {
        "status": "unavailable",
        "passed": False,
        "capability": capability,
        "error": "audit_provider_not_installed",
        "message": "真实审核提供方未安装，禁止伪造通过结果",
    }


def _optional_audit(capability: str, body: dict) -> tuple[HTTPStatus, dict]:
    _install_builtin_production_capabilities()
    if not PRODUCTION_CAPABILITIES.has(capability):
        return HTTPStatus.NOT_IMPLEMENTED, _unavailable_audit(capability)
    try:
        definition, result = PRODUCTION_CAPABILITIES.invoke_with_provider(capability, body=body)
        if not isinstance(result, dict):
            raise ValueError("audit result must be an object")
        status = str(result.get("status") or "")
        evidence = result.get("evidence")
        if status not in {"pass", "failed", "needs_fix"} or not evidence:
            raise ValueError("audit result lacks real evidence")
        return HTTPStatus.OK, {**result, "capability":capability, "provider_id":definition.provider_id}
    except Exception as error:
        return HTTPStatus.BAD_GATEWAY, {"status":"failed", "passed":False, "capability":capability, "error":"audit_provider_failed", "message":str(error)}


PRODUCTION_ENDPOINT_STAGES = {
    "/api/outline/plan":"outline", "/api/outline/episodes":"outline", "/api/script/episode":"script",
    "/api/storyboard":"storyboard", "/api/storyboard/shot":"storyboard",
    "/api/characters/generate":"image", "/api/shots/generate":"image", "/api/shots/repair":"image",
    "/api/assistant/images/generate":"image", "/api/assets/3d/generate":"assets",
    "/api/videos/generate":"video",
    "/api/audio/tts":"video", "/api/videos/lipsync":"video", "/api/videos/latentsync":"video",
    "/api/videos/merge":"composition", "/api/videos/audit":"review_export", "/api/exports/create":"review_export",
}
PRODUCTION_ENDPOINT_RESOURCES = {
    "/api/outline/plan":"text", "/api/outline/episodes":"text", "/api/script/episode":"text",
    "/api/storyboard":"text", "/api/storyboard/shot":"text", "/api/audit/narrative":"audit",
    "/api/characters/generate":"image", "/api/shots/generate":"image", "/api/shots/repair":"image",
    "/api/assistant/images/generate":"image",
    "/api/videos/generate":"video", "/api/audio/tts":"audio", "/api/videos/lipsync":"video",
    "/api/videos/latentsync":"video", "/api/videos/merge":"video", "/api/videos/audit":"audit",
    "/api/exports/create":"control", "/api/assets/3d/generate":"3d", "/api/images/upscale":"upscale", "/api/videos/upscale":"upscale",
}


def _is_asset_subtask_request(path: str, body: dict) -> bool:
    """Asset construction is input to the assets gate, not a downstream stage transition."""
    if path == "/api/assets/3d/generate":
        return True
    return (
        path == "/api/characters/generate"
        and str(body.get("asset_kind") or "").strip() in {"character", "scene", "prop"}
        and str(body.get("asset_phase") or "").strip() in {"baseline", "variant", "repair"}
    )


def _forward_production_request(path: str, body: dict, dispatched: bool) -> tuple[int, dict] | None:
    resource_class = PRODUCTION_ENDPOINT_RESOURCES.get(path) or ({"outline":"text", "script":"text", "storyboard":"text", "image":"image", "video":"video"}.get(str(body.get("stage"))) if path == "/api/production/run-stage" else None)
    if dispatched or not resource_class:
        return None
    _heartbeat_local_worker()
    explicit_request_id = str(body.get("request_id") or body.get("job_id") or "").strip()
    request_id = explicit_request_id or "dispatch-" + hashlib.sha256(json.dumps(
        {"path":path, "body":body}, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str,
    ).encode("utf-8")).hexdigest()
    worker = WORKER_REGISTRY.reserve(
        request_id, resource_class, estimated_memory=max(0, int(body.get("estimated_memory") or 0)),
        service_scope=WORKER_SCOPE, heartbeat_timeout=30, reservation_ttl=1950,
    )
    try:
        if worker.worker_id == WORKER_ID:
            return None
        if not worker.endpoint.startswith("http://") and not worker.endpoint.startswith("https://"):
            raise RuntimeError("selected worker has no dispatch endpoint")
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        request = Request(
            f"{worker.endpoint.rstrip('/')}{path}", data=payload, method="POST",
            headers={"Content-Type":"application/json", "X-Production-Dispatched":"1", "X-Production-Worker":worker.worker_id,
                     "X-Production-Reservation":request_id},
        )
        try:
            with urlopen(request, timeout=1900) as response:
                response_body = json.loads(response.read() or b"{}")
                if isinstance(response_body, dict): response_body["_dispatch"] = {"worker_id":worker.worker_id, "endpoint":worker.endpoint}
                return int(response.status), response_body
        except HTTPError as error:
            try: response_body = json.loads(error.read() or b"{}")
            except (ValueError, json.JSONDecodeError): response_body = {"error":"remote_worker_failed"}
            if int(error.code) in {502, 503, 504}:
                return int(HTTPStatus.SERVICE_UNAVAILABLE), {
                    "error":"workload_dispatch_failed", "message":str(response_body.get("message") or response_body.get("error") or "remote worker unavailable"),
                    "_dispatch":{"worker_id":worker.worker_id, "endpoint":worker.endpoint},
                }
            if isinstance(response_body, dict): response_body["_dispatch"] = {"worker_id":worker.worker_id, "endpoint":worker.endpoint}
            return int(error.code), response_body
    finally:
        WORKER_REGISTRY.release_reservation(request_id)


def _local_api(path: str, body: dict) -> dict:
    request = Request(f"http://127.0.0.1:{SERVICE_PORT}{path}", data=json.dumps(body, ensure_ascii=False).encode(), method="POST", headers={"Content-Type":"application/json", "X-Production-Dispatched":"1"})
    try:
        with urlopen(request, timeout=1900) as response: return json.loads(response.read() or b"{}")
    except HTTPError as error:
        try: payload = json.loads(error.read() or b"{}")
        except Exception: payload = {}
        raise RuntimeError(str(payload.get("error") or payload.get("message") or f"HTTP {error.code}")) from error


def _local_get(path: str) -> dict:
    with urlopen(Request(f"http://127.0.0.1:{SERVICE_PORT}{path}", headers={"X-Production-Dispatched":"1"}), timeout=30) as response:
        return json.loads(response.read() or b"{}")


def _checkpoint_production_stage(body: dict, stage: str) -> None:
    """Use the existing stage lease/cancel event as the only cancellation fact."""
    cancel_event = body.get("_cancel_event")
    if cancel_event is None:
        return
    if not hasattr(cancel_event, "is_set"):
        raise RuntimeError(f"production stage cancelled or lease lost: {stage}")
    if cancel_event.is_set():
        raise RuntimeError(f"production stage cancelled or lease lost: {stage}")
    if getattr(cancel_event, "lease_key", ""):
        _ensure_production_stage_request_active(cancel_event, stage)


def _production_stage_local_api(body: dict, stage: str, path: str, payload: dict) -> dict:
    _checkpoint_production_stage(body, stage)
    result = _local_api(path, payload)
    _checkpoint_production_stage(body, stage)
    return result


def _production_stage_local_get(body: dict, stage: str, path: str) -> dict:
    _checkpoint_production_stage(body, stage)
    result = _local_get(path)
    _checkpoint_production_stage(body, stage)
    return result


def _validated_review_export_authority(body: dict, command: dict, episodes: list[int], *, audit_required: bool) -> dict[int, dict]:
    """Validate authoritative audit when required and authoritative media always."""
    declarations = command.get("audit_results") or []
    if not isinstance(declarations, list):
        raise ValueError("review_export audit declarations must be a list")
    try:
        declaration_episodes = [int(item.get("episode") or 0) for item in declarations if isinstance(item, dict)]
    except (TypeError, ValueError):
        raise ValueError("review_export audit declaration requires a valid episode") from None
    if len(declaration_episodes) != len(declarations) or any(episode < 1 for episode in declaration_episodes) or len(set(declaration_episodes)) != len(declaration_episodes):
        raise ValueError("review_export audit declarations require unique valid episodes")
    declared = {episode:item for episode, item in zip(declaration_episodes, declarations)}
    source_version = str(command.get("source_version") or "").strip()
    if source_version not in {"base", "enhanced"}:
        raise ValueError("review_export source_version must be base or enhanced")
    all_records = PRODUCTION_LEDGER.list(body)
    records = {
        int(str(record.get("scope_id") or "").split(":", 1)[1]):record
        for record in all_records
        if record.get("stage") == "review_export" and record.get("scope_type") == "episode"
        and str(record.get("scope_id") or "").startswith("review:")
        and str(record.get("scope_id") or "").split(":", 1)[1].isdigit()
    }
    rejected: list[int] = []; authoritative_media: dict[int, dict] = {}
    for episode in episodes:
        declaration = declared.get(episode) or {}
        record = records.get(episode) or {}
        confirmation = record.get("confirmation") if isinstance(record.get("confirmation"), dict) else {}
        fingerprint = str(record.get("content_fingerprint") or "")
        audit_batch_id = str(record.get("audit_batch_id") or "")
        audit_valid = (
            declaration.get("status") == "pass"
            and declaration.get("confirmed") is True
            and record.get("lifecycle") == "completed"
            and bool(fingerprint and audit_batch_id and confirmation)
            and confirmation.get("content_fingerprint") == fingerprint
            and confirmation.get("audit_batch_id") == audit_batch_id
            and str(declaration.get("content_fingerprint") or "") == fingerprint
            and str(declaration.get("audit_batch_id") or "") == audit_batch_id
        )
        if audit_required and not audit_valid:
            rejected.append(episode)
            continue
        media_claim = next((item for item in command.get("items") or [] if isinstance(item, dict) and int(item.get("episode") or 0) == episode), {})
        media_fingerprint = str(media_claim.get("content_fingerprint") or "")
        media_batch_id = str(media_claim.get("audit_batch_id") or "")
        try:
            media_generation = int(media_claim.get("generation") or 0)
        except (TypeError, ValueError):
            media_generation = 0
        media_records = [record for record in all_records if (
            source_version == "base" and record.get("stage") == "composition" and record.get("scope_type") == "episode" and str(record.get("scope_id")) == str(episode)
        ) or (
            source_version == "enhanced" and record.get("stage") == "review_export" and record.get("scope_type") == "episode" and str(record.get("scope_id")) == f"upscale:{episode}"
        )]
        media_valid = any(
            item.get("lifecycle") == "completed"
            and bool(item.get("content_fingerprint") and item.get("audit_batch_id"))
            and item.get("content_fingerprint") == media_fingerprint
            and (source_version == "base" or bool(media_batch_id and item.get("audit_batch_id") == media_batch_id))
            and isinstance(item.get("confirmation"), dict)
            and item["confirmation"].get("content_fingerprint") == item.get("content_fingerprint")
            and item["confirmation"].get("audit_batch_id") == item.get("audit_batch_id")
            and (
                source_version == "base"
                or bool(
                    media_generation > 0
                    and int(item.get("generation") or 0) == media_generation
                    and int(item["confirmation"].get("generation") or 0) == media_generation
                )
            )
            for item in media_records
        )
        if not media_fingerprint or not media_valid:
            rejected.append(episode)
        else:
            selected_record = next(item for item in media_records if (
                item.get("lifecycle") == "completed"
                and item.get("content_fingerprint") == media_fingerprint
                and (source_version == "base" or item.get("audit_batch_id") == media_batch_id)
                and (source_version == "base" or int(item.get("generation") or 0) == media_generation)
                and isinstance(item.get("confirmation"), dict)
            ))
            production_evidence = selected_record.get("production_evidence")
            audit_evidence = selected_record.get("audit_evidence")
            if source_version == "enhanced":
                try:
                    _canonical_evidence_json(production_evidence, f"episode {episode} authoritative production evidence")
                    _canonical_evidence_json(audit_evidence, f"episode {episode} authoritative audit evidence")
                except RuntimeError:
                    rejected.append(episode)
                    continue
            authoritative_media[episode] = {
                "source_version":source_version, "content_fingerprint":selected_record["content_fingerprint"],
                "audit_batch_id":selected_record["audit_batch_id"],
                "generation":int(selected_record.get("generation") or 0),
                "production_evidence":production_evidence if production_evidence is not None else {"status":"not_available", "reason":"legacy_base_scope"},
                "audit_evidence":audit_evidence if audit_evidence is not None else {"status":"not_applicable", "reason":"legacy_base_scope"},
            }
    if rejected:
        raise ValueError(f"review_export export requires authoritative confirmed audit and media: {rejected}")
    return authoritative_media


def _storyboard_shot_key(shot: dict) -> tuple[int, int]:
    episode = int(shot.get("episode") or 0); shot_number = int(shot.get("shot_number") or 0)
    if episode <= 0 or shot_number <= 0:
        raise ValueError("storyboard shot requires positive episode and shot_number")
    return episode, shot_number


def _validated_storyboard_shots(shots: list[dict]) -> list[dict]:
    result: list[dict] = []; seen: set[tuple[int, int]] = set()
    for raw in shots:
        if not isinstance(raw, dict):
            raise ValueError("storyboard shots must be objects")
        key = _storyboard_shot_key(raw)
        if key in seen:
            raise ValueError(f"duplicate storyboard shot: {key[0]}:{key[1]}")
        seen.add(key); result.append(raw)
    return result


def _storyboard_episode_is_complete(shots: list[dict], script: dict, context: dict) -> bool:
    """Only a structurally complete, continuous episode may be resumed as authoritative."""
    if not 15 <= len(shots) <= 23:
        return False
    ordered = sorted(shots, key=lambda item:int(item.get("shot_number") or 0))
    if [int(item.get("shot_number") or 0) for item in ordered] != list(range(1, len(ordered) + 1)):
        return False
    target = float(script.get("target_duration") or context.get("duration") or 60)
    previous_end = 0.0
    for shot in ordered:
        try:
            start = float(shot.get("start_second")); end = float(shot.get("end_second"))
        except (TypeError, ValueError):
            return False
        if abs(start - previous_end) > .05 or end <= start or end - start < 2 or end - start > 9:
            return False
        previous_end = end
    return abs(previous_end - target) <= 1


def _validate_upscale_commands(commands: object) -> tuple[list[dict], list[int]]:
    """Validate the entire batch before the first mutating provider call."""
    if not isinstance(commands, list) or not commands:
        raise ValueError("review_export upscale requires at least one episode command")
    validated: list[dict] = []; episodes: list[int] = []
    for command in commands:
        if not isinstance(command, dict):
            raise ValueError("review_export upscale command must be an object")
        raw_episode = command.get("episode")
        if isinstance(raw_episode, bool):
            raise ValueError("review_export upscale command requires a positive integer episode")
        try:
            episode = int(raw_episode)
        except (TypeError, ValueError):
            raise ValueError("review_export upscale command requires a positive integer episode") from None
        if episode < 1 or str(raw_episode).strip() != str(episode):
            raise ValueError("review_export upscale command requires a positive integer episode")
        source = str(command.get("path") or command.get("source_url") or "").strip()
        parsed_source = urlparse(source)
        valid_source = bool(source) and (
            parsed_source.scheme in {"http", "https"} and bool(parsed_source.netloc)
            or source.startswith("/api/result-media?")
            or Path(source).is_absolute()
        )
        if not valid_source:
            raise ValueError(f"review_export upscale episode {episode} requires an absolute media path or URL")
        if str(command.get("source_version") or "") != "base":
            raise ValueError(f"review_export upscale episode {episode} source_version must be base")
        target = command.get("target")
        if not isinstance(target, dict):
            raise ValueError(f"review_export upscale episode {episode} requires target parameters")
        try:
            width, height, fps = (int(target.get(key) or 0) for key in ("width", "height", "fps"))
        except (TypeError, ValueError):
            raise ValueError(f"review_export upscale episode {episode} has invalid target parameters") from None
        if width < 1 or height < 1 or fps < 1 or str(target.get("mode") or "") not in {"quality", "speed"}:
            raise ValueError(f"review_export upscale episode {episode} has invalid target parameters")
        validated.append({**command, "episode":episode, "path":source}); episodes.append(episode)
    if len(set(episodes)) != len(episodes):
        raise ValueError("review_export upscale commands require unique episodes")
    return validated, episodes


def _canonical_evidence_json(value: object, label: str) -> str:
    if value is None or value == "" or value == {} or value == []:
        raise RuntimeError(f"{label} is empty")
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as error:
        raise RuntimeError(f"{label} is not canonical JSON: {error}") from error


def _run_server_production_stage(body: dict) -> dict:
    """Server-owned batching, retry and final audit for narrative stages."""
    stage = str(body.get("stage") or ""); context = dict(body.get("context") or {}); audit_enabled = bool(body.get("audit_enabled", False))
    _checkpoint_production_stage(body, stage)
    if stage == "outline":
        plan = _production_stage_local_api(body, stage, "/api/outline/plan", context)["plan"]; episodes: list[dict] = []
        total = int(context.get("episode_count") or 1); batch_size = max(1, int(body.get("batch_size") or 10))
        for start in range(1, total + 1, batch_size):
            _checkpoint_production_stage(body, stage)
            response = _production_stage_local_api(body, stage, "/api/outline/episodes", {**context, "plan":plan, "start_episode":start, "count":min(batch_size, total - start + 1), "total_episodes":total, "previous_episodes":episodes})
            episodes.extend(response.get("episodes") or [])
        audits: list[dict] = []
        if audit_enabled:
            _checkpoint_production_stage(body, stage)
            revised, audits = _audit_and_repair_narrative("outline", {**context, "range":"全剧", "_cancel_event":body.get("_cancel_event")}, {"plan":plan, "episodes":episodes})
            _checkpoint_production_stage(body, stage)
            plan = revised.get("plan") or plan; episodes = list(revised.get("episodes") or episodes)
        _checkpoint_production_stage(body, stage)
        return {"stage":"outline", "plan":plan, "episodes":episodes, "audit":audits[-1] if audits else None, "audits":audits}
    if stage == "script":
        plan = body.get("plan") or {}; outlines = list(body.get("episodes") or []); scripts: list[dict] = []
        for index, outline in enumerate(outlines):
            _checkpoint_production_stage(body, stage)
            last_error = ""
            for attempt in range(1, 3):
                _checkpoint_production_stage(body, stage)
                try:
                    response = _production_stage_local_api(body, stage, "/api/script/episode", {**context, "general_outline":plan.get("general_outline"), "episode_outline":outline, "all_episode_outlines":outlines, "previous_outline":outlines[index - 1] if index else None, "next_outline":outlines[index + 1] if index + 1 < len(outlines) else None, "previous_scripts":scripts, "characters":plan.get("characters", []), "retry_attempt":attempt, "retry_requirement":last_error})
                    scripts.append(response["script"]); break
                except RuntimeError as error:
                    last_error = str(error)
                    if attempt == 2: raise
        audits: list[dict] = []
        if audit_enabled:
            _checkpoint_production_stage(body, stage)
            revised, audits = _audit_and_repair_narrative("script", {**context, "range":"全剧", "_cancel_event":body.get("_cancel_event"), "upstream_context":{"outline_plan":plan, "episode_outlines":outlines}}, {"scripts":scripts})
            _checkpoint_production_stage(body, stage)
            scripts = list(revised.get("scripts") or scripts)
        _checkpoint_production_stage(body, stage)
        return {"stage":"script", "scripts":scripts, "audits":audits}
    if stage == "storyboard":
        scripts = list(body.get("scripts") or [])
        existing = _validated_storyboard_shots(list(body.get("shots") or context.get("shots") or context.get("existing_shots") or []))
        scripts_by_episode = {int(item.get("episode") or 0):item for item in scripts if isinstance(item, dict) and int(item.get("episode") or 0) > 0}
        if len(scripts_by_episode) != len(scripts):
            raise ValueError("storyboard scripts require unique positive episodes")
        unknown_existing = sorted({episode for episode, _ in map(_storyboard_shot_key, existing)} - set(scripts_by_episode))
        if unknown_existing:
            raise ValueError(f"existing storyboard contains episodes absent from scripts: {unknown_existing}")
        existing_by_episode = {episode:[item for item in existing if int(item.get("episode") or 0) == episode] for episode in scripts_by_episode}
        complete_episodes = {
            episode for episode, script in scripts_by_episode.items()
            if _storyboard_episode_is_complete(existing_by_episode.get(episode, []), script, context)
        }
        preserved = [item for item in existing if int(item.get("episode") or 0) in complete_episodes]
        generated: list[dict] = []; shots: list[dict] = list(preserved)
        cancel_event = body.get("_cancel_event")
        for script in scripts:
            episode = int(script.get("episode") or 0)
            if episode in complete_episodes:
                continue
            _checkpoint_production_stage(body, stage)
            response = _production_stage_local_api(body, stage, "/api/storyboard", {**context, "episode":episode, "script":script.get("content"), "duration":script.get("target_duration") or context.get("duration", 60), "characters":body.get("characters") or []})
            episode_shots = _validated_storyboard_shots(list((response.get("storyboard") or {}).get("shots") or []))
            if any(int(item.get("episode") or 0) != episode for item in episode_shots):
                raise ValueError(f"storyboard provider returned a foreign episode for {episode}")
            if not _storyboard_episode_is_complete(episode_shots, script, context):
                raise ValueError(f"storyboard provider returned an incomplete episode: {episode}")
            generated.extend(episode_shots); shots.extend(episode_shots)
            shots.sort(key=_storyboard_shot_key)
            _checkpoint_production_stage(body, stage)
            _write_storyboard_stream_progress(body, shots, episode, cancel_event if hasattr(cancel_event, "is_set") else threading.Event())
        audits: list[dict] = list(body.get("audits") or [])
        generated_episodes = sorted(set(scripts_by_episode) - complete_episodes)
        if audit_enabled and generated:
            _checkpoint_production_stage(body, stage)
            revised, new_audits = _audit_and_repair_narrative("storyboard", {**context, "range":f"分集{generated_episodes}", "_cancel_event":body.get("_cancel_event"), "upstream_context":{"scripts":[scripts_by_episode[item] for item in generated_episodes]}}, {"shots":generated})
            _checkpoint_production_stage(body, stage)
            revised_generated = _validated_storyboard_shots(list(revised.get("shots") or generated))
            if {int(item.get("episode") or 0) for item in revised_generated} != set(generated_episodes):
                raise ValueError("storyboard audit changed the generated episode scope")
            for episode in generated_episodes:
                audited_episode = [item for item in revised_generated if int(item.get("episode") or 0) == episode]
                if not _storyboard_episode_is_complete(audited_episode, scripts_by_episode[episode], context):
                    raise ValueError(f"storyboard audit returned an incomplete episode: {episode}")
            shots = sorted([*preserved, *revised_generated], key=_storyboard_shot_key)
            audits.extend(new_audits)
        _checkpoint_production_stage(body, stage)
        return {"stage":"storyboard", "shots":shots, "audits":audits, "generated_episodes":generated_episodes}
    if stage == "assets":
        extraction = _production_stage_local_api(body, stage, "/api/characters/extract", {
            **context,
            "outline": body.get("outline") or "",
            "scripts": body.get("scripts") or "",
            "extraction_phase": body.get("extraction_phase") or "manual",
            "target_episodes": body.get("target_episodes") or [],
            "required_characters": body.get("required_characters") or [],
            "style": body.get("style") or context.get("style") or "",
            "max_characters": body.get("max_characters") or 12,
        })
        _checkpoint_production_stage(body, stage)
        return {
            "stage":"assets",
            "characters":list(extraction.get("characters") or []),
            "scenes":list(extraction.get("scenes") or []),
            "props":list(extraction.get("props") or []),
            "census":dict(extraction.get("census") or {}),
        }
    if stage == "image":
        results = []
        for command in body.get("commands") or []:
            _checkpoint_production_stage(body, stage)
            generated = _production_stage_local_api(body, stage, "/api/shots/generate", command)["image"]
            audit_body = {**(command.get("identity") or {}), "image_url":generated["url"], "expected_visual":command.get("expected_visual"), "expected_characters":command.get("expected_characters", []), "references":command.get("references", [])}
            audit = _production_stage_local_api(body, stage, "/api/shots/semantic-audit", audit_body)
            repair_count = 0
            if not audit.get("passed"):
                repair_count = 1; issue = "；".join([*(audit.get("missing_subjects") or []), *(audit.get("contradictions") or []), str(audit.get("summary") or "")])
                generated = _production_stage_local_api(body, stage, "/api/shots/repair", {**command, "original_url":generated["url"], "issue":issue})["image"]
                audit = _production_stage_local_api(body, stage, "/api/shots/semantic-audit", {**audit_body, "image_url":generated["url"]})
            _checkpoint_production_stage(body, stage)
            results.append({"episode":command.get("episode"), "shot_number":command.get("shot_number"), "image_url":generated["url"], "status":"waiting_confirmation" if audit.get("passed") else "failed", "repair_count":repair_count, "audit_summary":audit.get("summary", ""), "error":"" if audit.get("passed") else f"复检未通过：{audit.get('summary', '')}"})
        _checkpoint_production_stage(body, stage)
        return {"stage":"image", "items":results}
    if stage == "video":
        results = []
        for command in body.get("commands") or []:
            _checkpoint_production_stage(body, stage)
            identity = command.get("identity") or {}; episode = int(command["episode"]); shot = int(command["shot_number"])
            _production_stage_local_api(body, stage, "/api/videos/generate", {**identity, **command.get("video", {})})
            video_result = {}
            for _ in range(900):
                _checkpoint_production_stage(body, stage)
                video_result = _production_stage_local_get(body, stage, f"/api/videos/result?{urlencode({**identity, 'episode':episode, 'shot_number':shot})}")
                if video_result.get("status") in {"completed", "failed", "stopped"}: break
                time.sleep(2)
            if video_result.get("status") != "completed": raise RuntimeError(str(video_result.get("error") or "分镜视频生成超时"))
            item = {"episode":episode, "shot_number":shot, "video_url":video_result.get("video", {}).get("url"), "source_video_url":video_result.get("video", {}).get("url"), "status":"waiting_confirmation", "voice_status":"not_applicable", "lip_sync_status":"not_applicable", "subtitle_status":"not_applicable", "audit_evidence":{"speaker":"not_applicable", "emotion":"not_applicable", "lipsync":"not_applicable", "face":"not_applicable", "continuity":"not_applicable"}}
            voice = command.get("voice") if isinstance(command.get("voice"), dict) else None
            if voice and voice.get("text"):
                audio = _production_stage_local_api(body, stage, "/api/audio/tts", {**identity, "episode":episode, "shot_number":shot, **voice})["audio"]
                item.update(audio_url=audio["url"], voice_status="completed", speaker=voice.get("character_name") or "旁白", voice_preset=voice.get("speaker"), voice_cast_version="qwen-1.7b-role-cast-v3", emotion=voice.get("emotion"), subtitle_status="completed")
                try: synced = _production_stage_local_api(body, stage, "/api/videos/lipsync", {**identity, "episode":episode, "shot_number":shot, "video_url":item["video_url"], "audio_url":item["audio_url"]})
                except RuntimeError:
                    _checkpoint_production_stage(body, stage)
                    synced = _production_stage_local_api(body, stage, "/api/videos/latentsync", {**identity, "episode":episode, "shot_number":shot, "video_url":item["video_url"], "audio_url":item["audio_url"], "inference_steps":8})
                item.update(video_url=synced.get("video_url"), path=synced.get("path"), lip_sync_status="completed", lip_sync_model=synced.get("model", "LatentSync-1.6"), lip_sync_version="server-media-package-v1")
            results.append(item)
        _checkpoint_production_stage(body, stage)
        return {"stage":"video", "items":results}
    if stage == "composition":
        commands = body.get("commands") or []
        if not commands:
            raise ValueError("composition requires at least one episode command")
        episodes: list[int] = []
        for command in commands:
            _checkpoint_production_stage(body, stage)
            if not isinstance(command, dict):
                raise ValueError("composition command requires a valid episode")
            try:
                episode = int(command.get("episode") or 0)
            except (TypeError, ValueError):
                raise ValueError("composition command requires a valid episode") from None
            if episode < 1:
                raise ValueError("composition command requires a valid episode")
            episodes.append(episode)
        if len(set(episodes)) != len(episodes):
            raise ValueError("composition episode commands must be unique")
        results = []
        for command, episode in zip(commands, episodes):
            _checkpoint_production_stage(body, stage)
            merged = _production_stage_local_api(body, stage, "/api/videos/merge", {**context, **command})
            results.append({"episode":episode, "status":"waiting_confirmation", **merged})
        _checkpoint_production_stage(body, stage)
        return {"stage":"composition", "items":results}
    if stage == "review_export":
        operation = str(body.get("operation") or "").strip().lower()
        if operation == "upscale":
            commands, episodes = _validate_upscale_commands(body.get("commands"))
            batch_id = "upscale-" + uuid4().hex
            identity = {key:str(body.get(key) or "").strip() for key in ("tenant_id", "user_id", "project_id")}
            generations = {
                episode: PRODUCTION_LEDGER.reserve_upscale_generation({
                    **identity, "stage":"review_export", "scope_type":"episode", "scope_id":f"upscale:{episode}",
                })
                for episode in episodes
            }
            results = []
            for command, episode in zip(commands, episodes):
                _checkpoint_production_stage(body, stage)
                enhanced = _production_stage_local_api(body, stage, "/api/videos/upscale", {**context, **command})
                path = str(enhanced.get("path") or "")
                if not path:
                    raise RuntimeError(f"episode {episode} upscale returned no media path")
                subtitles = command.get("subtitles") or []
                step_evidence: dict[str, dict] = {
                    "ocr":{"status":"not_applicable", "reason":"no_subtitles"},
                    "face":{"status":"not_applicable", "reason":"no_reference_urls"},
                }
                if subtitles:
                    ocr = _production_stage_local_api(body, stage, "/api/subtitles/ocr-audit", {**context, "path":path, "subtitles":subtitles})
                    if ocr.get("status") != "pass":
                        raise RuntimeError(f"episode {episode} enhanced subtitle audit failed")
                    ocr_evidence = ocr.get("evidence") if isinstance(ocr.get("evidence"), dict) else {}
                    if not ocr_evidence:
                        raise RuntimeError(f"episode {episode} enhanced subtitle audit lacks evidence")
                    step_evidence["ocr"] = {"status":"pass", "evidence":ocr_evidence}
                references = command.get("reference_urls") or []
                if references:
                    face = _production_stage_local_api(body, stage, "/api/videos/face-consistency-audit", {**context, "episode":episode, "video_url":enhanced.get("video_url"), "reference_urls":references})
                    if face.get("status") != "pass":
                        raise RuntimeError(f"episode {episode} enhanced face audit failed")
                    face_evidence = face.get("evidence") if isinstance(face.get("evidence"), dict) else {}
                    if not face_evidence:
                        raise RuntimeError(f"episode {episode} enhanced face audit lacks evidence")
                    step_evidence["face"] = {"status":"pass", "evidence":face_evidence}
                audit = _production_stage_local_api(body, stage, "/api/videos/audit", {**context, **command, "path":path, "video_url":enhanced.get("video_url"), "ocr_status":"pass" if subtitles else "not_applicable"})
                if audit.get("status") != "pass":
                    raise RuntimeError(f"episode {episode} enhanced final audit failed: {'；'.join(audit.get('issues') or [])}")
                production_evidence = enhanced.get("production_evidence")
                _canonical_evidence_json(production_evidence, f"episode {episode} production evidence")
                final_evidence = audit.get("evidence") if isinstance(audit.get("evidence"), dict) else {}
                if not final_evidence:
                    raise RuntimeError(f"episode {episode} enhanced output lacks authoritative evidence")
                step_evidence["final"] = {"status":"pass", "evidence":final_evidence}
                fingerprint_payload = {
                    "generation":generations[episode], "audit_batch_id":batch_id,
                    "command":command, "enhanced_output":enhanced,
                    "source":command["path"], "source_version":command["source_version"], "target":command["target"],
                    "production_evidence":production_evidence, "audit_evidence":step_evidence,
                }
                canonical_payload = _canonical_evidence_json(fingerprint_payload, f"episode {episode} upscale fingerprint payload")
                fingerprint = hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()
                results.append({"episode":episode, "status":"waiting_confirmation", **enhanced, "production_evidence":production_evidence, "audit_evidence":step_evidence, "content_fingerprint":fingerprint, "audit_batch_id":batch_id, "generation":generations[episode]})
            _checkpoint_production_stage(body, stage)
            authority_records = [{
                **identity, "stage":"review_export", "scope_type":"episode", "scope_id":f"upscale:{item['episode']}",
                "stage_substate":"upscale", "content_fingerprint":item["content_fingerprint"],
                "audit_batch_id":batch_id, "generation":item["generation"],
                "production_evidence":item["production_evidence"], "audit_evidence":item["audit_evidence"],
                "progress":{"completed":1, "total":1},
                "checkpoint":f"upscale:{batch_id}", "confirmation":None,
            } for item in results]
            # Authority publication is deliberately deferred to the stage
            # commit protocol.  Returning from physical execution must not
            # expose pending-confirmation evidence before cancellation loses.
            return {"stage":"review_export", "operation":"upscale", "items":results, "_authority_records":authority_records}
        if operation == "audit":
            commands = body.get("commands") or []
            if not isinstance(commands, list) or not commands:
                raise ValueError("review_export audit requires at least one episode command")
            episodes: list[int] = []
            for command in commands:
                _checkpoint_production_stage(body, stage)
                if not isinstance(command, dict):
                    raise ValueError("review_export audit command requires a valid episode")
                try:
                    episode = int(command.get("episode") or 0)
                except (TypeError, ValueError):
                    raise ValueError("review_export audit command requires a valid episode") from None
                if episode < 1:
                    raise ValueError("review_export audit command requires a valid episode")
                episodes.append(episode)
            if len(set(episodes)) != len(episodes):
                raise ValueError("review_export audit episode commands must be unique")
            results = []
            for command, episode in zip(commands, episodes):
                _checkpoint_production_stage(body, stage)
                max_attempts = max(1, min(2, int(command.get("max_attempts") or 2)))
                audit: dict = {"status":"needs_fix", "issues":["审核未返回结果"], "evidence":{}}
                attempts = 0
                for attempt in range(1, max_attempts + 1):
                    _checkpoint_production_stage(body, stage)
                    attempts = attempt
                    try:
                        audit = _production_stage_local_api(body, stage, "/api/videos/audit", {**context, **command, "audit_attempt":attempt})
                    except RuntimeError as error:
                        _checkpoint_production_stage(body, stage)
                        audit = {"status":"needs_fix", "issues":[str(error)], "evidence":{"error_type":type(error).__name__, "attempt":attempt}}
                        if attempt < max_attempts:
                            continue
                    break
                if audit.get("status") not in {"pass", "needs_fix"}:
                    audit = {**audit, "status":"needs_fix", "issues":[*(audit.get("issues") or []), "审核返回了非法状态"]}
                results.append({"episode":episode, **audit, "attempts":attempts})
            _checkpoint_production_stage(body, stage)
            return {"stage":"review_export", "operation":"audit", "items":results}
        if operation == "export":
            command = body.get("command")
            if not isinstance(command, dict):
                raise ValueError("review_export export requires one export command")
            items = command.get("items") or []
            if not isinstance(items, list) or not items:
                raise ValueError("review_export export requires at least one media item")
            try:
                episodes = [int(item.get("episode") or 0) for item in items if isinstance(item, dict)]
            except (TypeError, ValueError):
                raise ValueError("review_export export item requires a valid episode") from None
            if len(episodes) != len(items) or any(episode < 1 for episode in episodes):
                raise ValueError("review_export export item requires a valid episode")
            if len(set(episodes)) != len(episodes):
                raise ValueError("review_export export episode items must be unique")
            authority = _validated_review_export_authority(body, command, episodes, audit_required=bool(command.get("audit_required", True)))
            command = {**command, "items":[{**item, **authority[int(item["episode"])]} for item in items]}
            _checkpoint_production_stage(body, stage)
            exported = _production_stage_local_api(body, stage, "/api/exports/create", {**context, **command})
            _checkpoint_production_stage(body, stage)
            return {"stage":"review_export", "operation":"export", **exported}
        raise ValueError("review_export operation must be audit or export")
    raise ValueError("unsupported server narrative stage")


def _validated_composition_media_packages(records: list[dict]) -> dict[str, str]:
    """Return shot -> media package batch after validating authoritative evidence."""
    evidence: dict[str, dict[str, str]] = {stage: {} for stage in ("video", "audio", "subtitle")}
    for record in records:
        stage = str(record.get("stage") or "")
        if stage not in evidence or record.get("scope_type") != "shot" or record.get("lifecycle") != "completed":
            continue
        scope_id = str(record.get("scope_id") or "").strip()
        content_fingerprint = str(record.get("content_fingerprint") or "").strip()
        audit_batch_id = str(record.get("audit_batch_id") or "").strip()
        confirmation = record.get("confirmation") if isinstance(record.get("confirmation"), dict) else {}
        if not scope_id or not content_fingerprint or not audit_batch_id:
            continue
        if confirmation.get("content_fingerprint") != content_fingerprint or confirmation.get("audit_batch_id") != audit_batch_id:
            continue
        evidence[stage][scope_id] = audit_batch_id
    shot_ids = set(evidence["video"])
    if not shot_ids or shot_ids != set(evidence["audio"]) or shot_ids != set(evidence["subtitle"]):
        raise ValueError("composition requires confirmed video/audio/subtitle evidence for every shot")
    for shot_id in shot_ids:
        batches = {evidence[stage][shot_id] for stage in ("video", "audio", "subtitle")}
        if len(batches) != 1:
            raise ValueError(f"composition media package mismatch for shot {shot_id}")
    return {shot_id: evidence["video"][shot_id] for shot_id in sorted(shot_ids)}


def _current_stage_report_fence(brain: Any, identity: dict, stage: str) -> dict[str, int]:
    """Advance an already leased stage event without inventing a new owner."""
    if not callable(getattr(brain, "state", None)):
        return {}
    state = brain.state(identity)
    generation = int((state.get("stage_generations") or {}).get(stage) or 0)
    if generation <= 0:
        return {}
    revision = int((state.get("projection_revisions") or {}).get(stage) or 0)
    return {"stage_generation":generation, "projection_revision":revision + 1}


def _confirm_production_scope(payload: dict) -> tuple[dict, dict]:
    brain = _production_orchestrator(); stage = canonical_stage(payload.get("stage"))
    candidate = next((item for item in PRODUCTION_LEDGER.list(payload) if item["stage"] == stage and item["scope_type"] == str(payload.get("scope_type")) and item["scope_id"] == str(payload.get("scope_id"))), None)
    if not candidate: raise ProductionLedgerError("production scope does not exist")
    if stage == "review_export" and str(payload.get("scope_type")) == "episode" and str(payload.get("scope_id") or "").startswith("upscale:"):
        try:
            claimed_generation = int(payload.get("generation") or 0)
        except (TypeError, ValueError):
            claimed_generation = 0
        if not (
            claimed_generation > 0
            and claimed_generation == int(candidate.get("generation") or 0)
            and str(payload.get("content_fingerprint") or "") == str(candidate.get("content_fingerprint") or "")
            and str(payload.get("audit_batch_id") or "") == str(candidate.get("audit_batch_id") or "")
        ):
            raise ProductionLedgerError("upscale confirmation requires the current authoritative generation")
    proposed_confirmation = {"content_fingerprint":candidate["content_fingerprint"], "audit_batch_id":candidate["audit_batch_id"], "generation":int(candidate.get("generation") or 0), "confirmed_by":str(payload.get("user_id")), "confirmed_at":_iso_now()}
    brain.validate_completion(payload, stage, confirmation=proposed_confirmation)
    record = PRODUCTION_LEDGER.confirm(payload)
    try:
        all_records = PRODUCTION_LEDGER.list(payload)
        stage_records = _stage_gate_records(stage, all_records)
        lifecycle = "completed" if stage_records and _production_stage_gate_complete(stage, all_records) else "pending_confirmation"
        workflow = brain.report(
            payload, stage, lifecycle, confirmation=record["confirmation"],
            **_current_stage_report_fence(brain, payload, stage),
        )
    except Exception:
        PRODUCTION_LEDGER.restore_pending_confirmation(payload, "LangGraph确认提交失败，已回滚")
        raise
    return record, workflow


def _confirm_asset_scope_deferred(payload: dict) -> tuple[dict, dict]:
    """Confirm one asset now, but defer aggregate stage promotion until storyboard completes."""
    brain = _production_orchestrator()
    candidate = next((item for item in PRODUCTION_LEDGER.list(payload) if (
        item["stage"] == "assets"
        and item["scope_type"] == str(payload.get("scope_type"))
        and item["scope_id"] == str(payload.get("scope_id"))
    )), None)
    if not candidate:
        raise ProductionLedgerError("production scope does not exist")
    record = PRODUCTION_LEDGER.confirm(payload)
    try:
        proposed = record.get("confirmation") or {}
        brain.validate_completion(payload, "assets", confirmation=proposed)
    except ValueError as error:
        if not str(error).startswith("previous stage is not completed:"):
            PRODUCTION_LEDGER.restore_pending_confirmation(payload, "资产确认校验失败，已回滚")
            raise
        workflow = brain.report(
            payload, "assets", "pending_confirmation",
            deferred_confirmation=True, deferred_reason=str(error), confirmed_asset_scope=str(payload.get("scope_id") or ""),
            **_current_stage_report_fence(brain, payload, "assets"),
        )
        return record, workflow
    try:
        all_records = PRODUCTION_LEDGER.list(payload)
        stage_records = _stage_gate_records("assets", all_records)
        lifecycle = "completed" if stage_records and _production_stage_gate_complete("assets", all_records) else "pending_confirmation"
        workflow = brain.report(
            payload, "assets", lifecycle, confirmation=record.get("confirmation"),
            **_current_stage_report_fence(brain, payload, "assets"),
        )
    except Exception:
        PRODUCTION_LEDGER.restore_pending_confirmation(payload, "LangGraph确认提交失败，已回滚")
        raise
    return record, workflow


def _confirmed_production_gate_record(record: dict) -> bool:
    """One shared definition for facts that may promote a production stage."""
    confirmation = record.get("confirmation")
    if record.get("lifecycle") != "completed" or not isinstance(confirmation, dict) or not confirmation:
        return False
    if str(record.get("stage") or "") in {"image", "video", "audio", "subtitle"} and record.get("scope_type") == "shot":
        fingerprint = str(record.get("content_fingerprint") or "").strip()
        audit_batch_id = str(record.get("audit_batch_id") or "").strip()
        return bool(
            fingerprint
            and audit_batch_id
            and str(confirmation.get("content_fingerprint") or "").strip() == fingerprint
            and str(confirmation.get("audit_batch_id") or "").strip() == audit_batch_id
        )
    return True


def _shot_scope_parts(scope_id: object) -> tuple[int, int] | None:
    raw = str(scope_id or "")
    match = re.fullmatch(r"([1-9]\d*):([1-9]\d*)", raw)
    if not match:
        return None
    parts = (int(match.group(1)), int(match.group(2)))
    return parts if raw == f"{parts[0]}:{parts[1]}" else None


def _media_stage_gate_records(stage: str, records: list[dict]) -> list[dict]:
    """Return every actual media scope plus explicit fail-closed gate facts."""
    stage_records = [record for record in records if str(record.get("stage") or "") == stage]
    if not stage_records:
        return []
    failures: list[dict] = []

    def failure(scope_id: str, error: str) -> None:
        failures.append({
            "stage":stage, "scope_type":"shot", "scope_id":scope_id,
            "lifecycle":"stale", "confirmation":None, "error":error, "_gate_error":True,
        })

    expected_by_episode: dict[int, set[str]] = {}
    seen_expected: set[str] = set()
    for record in records:
        if str(record.get("stage") or "") != "storyboard" or record.get("scope_type") != "shot":
            continue
        raw_scope = str(record.get("scope_id") or "")
        parts = _shot_scope_parts(raw_scope)
        if not parts:
            failure(f"invalid-storyboard:{raw_scope}", "storyboard shot scope is invalid or non-canonical")
            continue
        canonical = f"{parts[0]}:{parts[1]}"
        if canonical in seen_expected:
            failure(f"duplicate-storyboard:{canonical}", "storyboard shot census contains a duplicate or alias collision")
            continue
        seen_expected.add(canonical)
        expected_by_episode.setdefault(parts[0], set()).add(canonical)
    if not expected_by_episode:
        failure("missing-storyboard-census", "storyboard shot census is required")

    actual_by_scope: dict[str, dict] = {}
    for record in stage_records:
        raw_scope = str(record.get("scope_id") or "")
        if record.get("scope_type") != "shot":
            failure(f"invalid-scope-type:{raw_scope}", "media stage only accepts shot scopes")
            continue
        parts = _shot_scope_parts(raw_scope)
        if not parts:
            failure(f"invalid-media:{raw_scope}", "media shot scope is invalid or non-canonical")
            continue
        canonical = f"{parts[0]}:{parts[1]}"
        if canonical in actual_by_scope:
            failure(f"duplicate-media:{canonical}", "media shot scope contains a duplicate or alias collision")
            continue
        actual_by_scope[canonical] = record
        if canonical not in seen_expected:
            failure(f"unexpected-media:{canonical}", "media shot scope is outside the authoritative storyboard census")

    complete_episode = any(
        expected and all(
            scope_id in actual_by_scope and _confirmed_production_gate_record(actual_by_scope[scope_id])
            for scope_id in expected
        )
        for expected in expected_by_episode.values()
    )
    if not complete_episode:
        failure("incomplete-episode-coverage", "no episode has complete confirmed media shot coverage")
    return [*stage_records, *failures]


def _stage_gate_records(stage: str, records: list[dict]) -> list[dict]:
    """Select the exact durable scopes whose confirmation promotes one stage.

    Shot stages use the confirmed storyboard census as their expected set.  A
    stage is promotable when at least one episode has every expected shot; one
    present/confirmed row must never stand in for missing sibling shots.
    """
    stage_records = [record for record in records if str(record.get("stage") or "") == stage]
    if not stage_records:
        return []
    if stage in {"image", "video", "audio", "subtitle"}:
        return _media_stage_gate_records(stage, records)
    scope_types = {str(record.get("scope_type") or "") for record in stage_records}
    preferred: tuple[str, ...]
    if stage == "requirements":
        preferred = ("project",)
    elif stage == "outline":
        preferred = ("project", "episode")
    elif stage in {"script", "storyboard"}:
        preferred = ("story_arc_batch", "episode_batch", "episode")
    elif stage == "assets":
        preferred = ("asset",)
    elif stage in {"composition", "review_export"}:
        preferred = ("episode_batch", "episode")
    else:
        preferred = tuple(sorted(scope_types))
    # A batch confirmation explicitly covers its member episodes. When a batch
    # exists it is the aggregate gate; episode/line/shot rows remain auditable
    # detail and must not require hundreds of duplicate human confirmations.
    for scope_type in preferred:
        selected = [record for record in stage_records if record.get("scope_type") == scope_type]
        if selected:
            return selected
    return stage_records


def _production_stage_gate_complete(stage: str, records: list[dict]) -> bool:
    gate_records = _stage_gate_records(stage, records)
    if not gate_records:
        return False
    if stage in {"image", "video", "audio", "subtitle"}:
        return not any(record.get("_gate_error") is True for record in gate_records)
    return all(_confirmed_production_gate_record(record) for record in gate_records)


def _reconcile_completed_production_stages(identity: dict, records: list[dict]) -> dict:
    """Heal a stale LangGraph projection from durable confirmed ledger facts."""
    brain = _production_orchestrator()
    state = brain.state(identity)
    for stage in CANONICAL_STAGES:
        stage_records = _stage_gate_records(stage, records)
        if not stage_records:
            break
        complete = _production_stage_gate_complete(stage, records)
        if not complete:
            break
        if state.get("stages", {}).get(stage) != "completed":
            confirmation = next(record["confirmation"] for record in stage_records if isinstance(record.get("confirmation"), dict))
            state = brain.report(
                identity, stage, "completed", confirmation=confirmation,
                reconciled_from="production_ledger",
                **_current_stage_report_fence(brain, identity, stage),
            )
    return state


def _recover_production_workflows() -> None:
    """Fail synchronous stage executions that cannot survive a service restart."""
    brain = _production_orchestrator()
    stage_storage = {
        "outline":"outline", "script":"script", "storyboard":"storyboard", "assets":"assets",
        "image":"shot_images", "video":"shot_videos", "composition":"merged_episodes", "review_export":"final_audit",
    }
    for project in _load_store().get("projects", []):
        identity = {key:str(project.get(key) or "") for key in ("tenant_id", "user_id")}
        identity["project_id"] = str(project.get("id") or "")
        if not all(identity.values()):
            continue
        state = brain.state(identity)
        current_stage = str(state.get("current_stage") or "")
        event = state.get("event") if isinstance(state.get("event"), dict) else {}
        authority_commit = event.get("authority_commit") if isinstance(event, dict) else None
        if (
            current_stage == "review_export"
            and state.get("stages", {}).get(current_stage) == "pending_confirmation"
            and isinstance(authority_commit, dict)
            and authority_commit.get("kind") == "upscale"
        ):
            expected = authority_commit.get("records") if isinstance(authority_commit.get("records"), list) else []
            actual = {
                (str(item.get("scope_id") or ""), int(item.get("generation") or 0),
                 str(item.get("content_fingerprint") or ""), str(item.get("audit_batch_id") or ""))
                for item in PRODUCTION_LEDGER.list(identity)
                if item.get("stage") == "review_export" and str(item.get("scope_id") or "").startswith("upscale:")
            }
            expected_keys = {
                (str(item.get("scope_id") or ""), int(item.get("generation") or 0),
                 str(item.get("content_fingerprint") or ""), str(item.get("audit_batch_id") or ""))
                for item in expected if isinstance(item, dict)
            }
            if not expected_keys or not expected_keys.issubset(actual):
                brain.report(
                    identity, current_stage, "failed",
                    error="服务重启检测到未完成的增强权威提交，已失败关闭",
                    stage_generation=int(event.get("stage_generation") or 0),
                    projection_revision=int(event.get("projection_revision") or 0) + 1,
                )
                continue
        if current_stage and state.get("stages", {}).get(current_stage) == "running":
            storage_stage = stage_storage.get(current_stage, "")
            stored = project.get("stage_state", {}).get(storage_stage) if storage_stage else None
            if isinstance(stored, dict) and isinstance(stored.get("data"), dict):
                recovered = dict(stored["data"])
                recovered.update({"status":"failed", "error":"服务重启已回收未完成生产阶段"})
                _write_project_stage(identity["project_id"], identity["tenant_id"], identity["user_id"], storage_stage, recovered)
            else:
                brain.report(identity, current_stage, "failed", error="服务重启已回收未完成生产阶段",
                    **_current_stage_report_fence(brain, identity, current_stage),
                )


def _begin_production_request(body: dict, stage: str, *, stage_generation: int = 0) -> dict:
    identity = {
        "tenant_id":str(body.get("tenant_id") or "local-default").strip(),
        "user_id":str(body.get("user_id") or "aoo").strip(),
        "project_id":str(body.get("project_id") or "").strip(),
    }
    if not all(identity.values()):
        raise ValueError("tenant_id, user_id and project_id are required")
    brain = _production_orchestrator()
    state = brain.state(identity)
    stages = state.get("stages", {})
    if not stages.get("requirements"):
        project_exists = any(
            str(item.get("id")) == identity["project_id"] and str(item.get("tenant_id")) == identity["tenant_id"] and str(item.get("user_id")) == identity["user_id"]
            for item in _load_store().get("projects", [])
        )
        if not project_exists:
            raise ValueError("project does not exist")
        brain.report(identity, "requirements", "completed", trusted=True, evidence={"source":"project_store"})
    records = PRODUCTION_LEDGER.list(identity)
    _reconcile_completed_production_stages(identity, records)
    if stage == "composition":
        _validated_composition_media_packages(records)
    return brain.begin(identity, stage, stage_generation=stage_generation)


class Handler(BaseHTTPRequestHandler):
    server_version = "ShortDramaCompatibilityAPI"

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            _install_builtin_production_capabilities()
            return self._json(HTTPStatus.OK, {"status": "healthy", "service": "short-drama-data", "orchestrator":"langgraph", "resources":RESOURCE_SCHEDULER.snapshot(), "capabilities":[{"capability":item.capability,"provider_id":item.provider_id,"enabled":item.enabled,"healthy":item.healthy,"priority":item.priority} for item in PRODUCTION_CAPABILITIES.list()]})
        if parsed.path == "/api/health":
            return self._json(HTTPStatus.OK, {"status": "healthy", "models": {
                "light": TEXT_LIGHT_MODEL,
                "formal": TEXT_FORMAL_MODEL,
                "audit": TEXT_AUDIT_MODEL,
            }})
        if parsed.path == "/api/lora/styles":
            return self._json(HTTPStatus.OK, {"root": str(LORA_ROOT), "styles": _scan_lora_style_directories()})
        if parsed.path == "/api/assistant/capabilities":
            return self._json(HTTPStatus.OK, {"models": [
                {"name":TEXT_LIGHT_MODEL, "role":"分集梗概与轻量任务", "selected":True},
                {"name":TEXT_FORMAL_MODEL, "role":"故事总纲、正式剧本与分镜", "selected":True},
                {"name":TEXT_AUDIT_MODEL, "role":"大纲、剧本与分镜初审终审", "selected":True},
            ], "skills": ["项目对话", "短剧策划", "资源查询", "联网搜索与来源核验"], "web_search":{"available":True,"providers":list(WEB_SEARCH_PROVIDER_DESCRIPTIONS)}})
        if parsed.path == "/api/assistant/agents/status":
            job_id = parse_qs(parsed.query).get("job_id", [""])[0]
            with AGENT_JOB_LOCK:
                job = _load_agent_jobs().get("jobs", {}).get(job_id)
            if not job: return self._json(HTTPStatus.NOT_FOUND, {"error":"agent_job_not_found"})
            payload = {key:value for key, value in job.items() if key not in {"context"}}
            payload["heartbeat_at"] = datetime.now(UTC).isoformat()
            return self._json(HTTPStatus.OK, payload)
        if parsed.path == "/api/assets/3d/status":
            job_id = parse_qs(parsed.query).get("job_id", [""])[0]
            job = _load_image_jobs().get("jobs", {}).get(job_id)
            if not job or job.get("workflow") != "asset_3d":
                return self._json(HTTPStatus.NOT_FOUND, {"error":"asset_3d_job_not_found"})
            return self._json(HTTPStatus.OK, dict(job))
        if parsed.path == "/api/projects":
            query = parse_qs(parsed.query)
            tenant = query.get("tenant_id", [""])[0]
            user = query.get("user_id", [""])[0]
            include_archived = query.get("include_archived", ["false"])[0] == "true"
            with PROJECT_STORE_LOCK:
                projects = [item for item in _load_store().get("projects", []) if item.get("tenant_id") == tenant and item.get("user_id") == user and (include_archived or not item.get("archived"))]
            return self._json(HTTPStatus.OK, {"projects": projects})
        if parsed.path == "/api/projects/stage":
            query = parse_qs(parsed.query)
            project = self._project(query.get("id", [""])[0], query.get("tenant_id", [""])[0], query.get("user_id", [""])[0])
            if not project:
                return self._json(HTTPStatus.NOT_FOUND, {"error": "project_not_found"})
            return self._json(HTTPStatus.OK, {"stage": project.get("stage_state", {}).get(query.get("stage", [""])[0])})
        if parsed.path == "/api/projects/stage/watch":
            query = parse_qs(parsed.query)
            project_id = query.get("id", [""])[0]; tenant_id = query.get("tenant_id", [""])[0]; user_id = query.get("user_id", [""])[0]
            stage_name = query.get("stage", [""])[0]
            request_id = query.get("request_id", [""])[0].strip()
            try: watch_key = _project_stage_watch_key(tenant_id, user_id, project_id, stage_name, request_id)
            except ValueError: return self._json(HTTPStatus.BAD_REQUEST, {"error":"invalid_watch_scope"})
            try: after_revision = max(0, int(query.get("after_revision", ["0"])[0] or 0))
            except ValueError: return self._json(HTTPStatus.BAD_REQUEST, {"error":"invalid_stage_revision"})
            try: timeout_seconds = min(25.0, max(0.0, float(query.get("timeout_seconds", ["20"])[0] or 20)))
            except ValueError: return self._json(HTTPStatus.BAD_REQUEST, {"error":"invalid_watch_timeout"})
            if not PROJECT_STAGE_WATCH_SLOTS.acquire(blocking=False):
                return self._json(HTTPStatus.TOO_MANY_REQUESTS, {"error":"stage_watch_backpressure", "retry_after_ms":1000})
            deadline = time.monotonic() + timeout_seconds
            response_status = HTTPStatus.OK; response_payload: dict = {}
            try:
                with PROJECT_STAGE_CONDITION:
                    while True:
                        if SERVICE_SHUTTING_DOWN.is_set():
                            response_status = HTTPStatus.SERVICE_UNAVAILABLE; response_payload = {"error":"service_shutting_down", "changed":False, "cancelled":True, "stage":None}; break
                        if watch_key in PROJECT_STAGE_CANCELLED_WATCHES:
                            response_payload = {"changed":False, "cancelled":True, "stage":None}; break
                        project = next((item for item in _load_store().get("projects", []) if item.get("id") == project_id and item.get("tenant_id") == tenant_id and item.get("user_id") == user_id), None)
                        if not project:
                            response_status = HTTPStatus.NOT_FOUND; response_payload = {"error":"project_not_found"}; break
                        stage = project.get("stage_state", {}).get(stage_name)
                        revision = int((stage or {}).get("revision", 0) or 0)
                        if revision > after_revision:
                            response_payload = {"changed":True, "stage":stage}; break
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            response_payload = {"changed":False, "stage":stage}; break
                        PROJECT_STAGE_CONDITION.wait(remaining)
            finally:
                with PROJECT_STAGE_CONDITION:
                    PROJECT_STAGE_CANCELLED_WATCHES.pop(watch_key, None)
                PROJECT_STAGE_WATCH_SLOTS.release()
            return self._json(response_status, response_payload)
        if parsed.path == "/api/projects/version":
            query = parse_qs(parsed.query); project_id = query.get("project_id", [""])[0]; version_id = query.get("version_id", [""])[0]
            if version_id:
                record = _read_project_version(version_id)
                if not record or str(record.get("project_id", "")) != project_id:
                    return self._json(HTTPStatus.NOT_FOUND, {"error":"version_not_found"})
                return self._json(HTTPStatus.OK, {"version":record})
            versions = []
            if PROJECT_VERSIONS_DIR.is_dir():
                for path in sorted(PROJECT_VERSIONS_DIR.glob("*.json"), reverse=True):
                    record = _read_project_version(path.stem)
                    if record and str(record.get("project_id", "")) == project_id:
                        versions.append({key:value for key, value in record.items() if key != "project"})
            return self._json(HTTPStatus.OK, {"versions":versions})
        if parsed.path == "/api/tasks":
            query = parse_qs(parsed.query)
            tasks = _project_tasks(query.get("tenant_id", [""])[0], query.get("user_id", [""])[0], query.get("project_id", [""])[0])
            return self._json(HTTPStatus.OK, {"tasks": tasks, "fault": None})
        if parsed.path == "/api/tasks/runtime":
            query = parse_qs(parsed.query)
            repository = _task_repository(TEXT_JOBS_FILE)
            tasks = repository.list(
                tenant_id=query.get("tenant_id", [""])[0],
                user_id=query.get("user_id", [""])[0],
                project_id=query.get("project_id", [""])[0],
                nonterminal_only=query.get("nonterminal_only", ["false"])[0] == "true",
            )
            return self._json(HTTPStatus.OK, {"tasks":tasks})
        if parsed.path == "/api/tasks/result":
            query = parse_qs(parsed.query); operation_key = query.get("operation_key", [""])[0]
            tasks = _project_tasks(query.get("tenant_id", [""])[0], query.get("user_id", [""])[0], query.get("project_id", [""])[0])
            task = next((item for item in tasks if item["operation_key"] == operation_key), None)
            if not task: return self._json(HTTPStatus.NOT_FOUND, {"error":"task_not_found"})
            return self._json(HTTPStatus.OK, {"task":task, "result":{"status":task["status"], "scope_id":task["scope_id"]} if task["has_result"] else None})
        if parsed.path == "/api/resources":
            query = parse_qs(parsed.query)
            resources = [item for item in _load_resources().get("resources", []) if all(not query.get(key) or str(item.get(key, "")) == query[key][0] for key in ("tenant_id", "user_id", "project_id"))]
            return self._json(HTTPStatus.OK, {"resources": resources})
        if parsed.path == "/api/production/scopes":
            query = parse_qs(parsed.query)
            identity = {key: query.get(key, [""])[0] for key in ("tenant_id", "user_id", "project_id")}
            try:
                return self._json(HTTPStatus.OK, {"records": PRODUCTION_LEDGER.list(identity)})
            except ProductionLedgerError as error:
                return self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid_production_scope", "message": str(error)})
        if parsed.path == "/api/production/versions":
            query = parse_qs(parsed.query)
            identity = {key: query.get(key, [""])[0] for key in ("tenant_id", "user_id", "project_id")}
            try:
                return self._json(HTTPStatus.OK, {"versions": PRODUCTION_LEDGER.versions(identity)})
            except ProductionLedgerError as error:
                return self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid_production_scope", "message": str(error)})
        if parsed.path == "/api/production/workflow":
            query = parse_qs(parsed.query)
            identity = {key: query.get(key, [""])[0] for key in ("tenant_id", "user_id", "project_id")}
            try:
                orchestrator = _production_orchestrator()
                return self._json(HTTPStatus.OK, {"workflow": orchestrator.state(identity), "stage_executors":[{"stage":item.stage,"provider_id":item.provider_id,"enabled":item.enabled} for item in orchestrator.stages()]})
            except (ProductionLedgerError, ValueError) as error:
                return self._json(HTTPStatus.BAD_REQUEST, {"error":"invalid_production_workflow", "message":str(error)})
        if parsed.path == "/api/production/capabilities":
            _install_builtin_production_capabilities()
            _heartbeat_local_worker()
            return self._json(HTTPStatus.OK, {
                "capabilities":[{"capability":item.capability,"provider_id":item.provider_id,"enabled":item.enabled,"healthy":item.healthy,"priority":item.priority,"metadata":dict(item.metadata)} for item in PRODUCTION_CAPABILITIES.list()],
                "extensions":[{"extension_point":item.extension_point,"provider_id":item.provider_id,"enabled":item.enabled,"active":item.active,"metadata":dict(item.metadata)} for item in PRODUCTION_EXTENSIONS.list()],
                "workers":WORKLOAD_ROUTER.snapshot(),
            })
        if parsed.path == "/api/production/workers":
            _heartbeat_local_worker()
            return self._json(HTTPStatus.OK, {"workers":WORKLOAD_ROUTER.snapshot(), "resources":RESOURCE_SCHEDULER.snapshot()})
        if parsed.path == "/api/production/story-bible":
            query = parse_qs(parsed.query)
            identity = {key: query.get(key, [""])[0] for key in ("tenant_id", "user_id", "project_id")}
            try:
                return self._json(HTTPStatus.OK, {"story_bible":STORY_BIBLE.read(identity)})
            except StoryBibleError as error:
                return self._json(HTTPStatus.BAD_REQUEST, {"error":"invalid_story_bible", "message":str(error)})
        if parsed.path in {"/api/result-media", "/api/media"}:
            return self._media(parsed)
        if parsed.path == "/api/characters/result":
            name = parse_qs(parsed.query).get("name", [""])[0]
            stored_jobs = _load_image_jobs().get("jobs", {})
            matches = [(job_id, item) for job_id, item in stored_jobs.items() if item.get("request_name") == name or job_id == name]
            job_id, job = max(matches, key=lambda pair:_parse_job_time(pair[1].get("started_at"))) if matches else ("", None)
            if job and job.get("status") == "generating" and job_id not in ACTIVE_IMAGE_JOBS:
                job = {"status":"failed", "error":"图片任务已中断，请点击继续生成", "finished_at":datetime.now(UTC).isoformat()}
                with IMAGE_JOB_LOCK:
                    jobs = _load_image_jobs(); jobs.setdefault("jobs", {})[job_id] = job; _save_image_jobs(jobs)
            return self._json(HTTPStatus.OK if job else HTTPStatus.NOT_FOUND, job or {"error": "image_not_found"})
        if parsed.path == "/api/videos/result":
            query = parse_qs(parsed.query)
            subject_key = ":".join(query.get(name, [""])[0] for name in ("tenant_id", "user_id", "project_id", "episode", "shot_number"))
            matches = [(job_id, job) for job_id, job in _load_video_jobs().get("jobs", {}).items() if job.get("subject_key") == subject_key or job_id == query.get("job_id", [""])[0]]
            job_id, job = max(matches, key=lambda pair:_parse_job_time(pair[1].get("queued_at"))) if matches else ("", None)
            if job and job.get("status") == "generating" and job_id not in ACTIVE_VIDEO_JOBS:
                terminal_error = "视频任务已中断，请点击继续生成"
                if _cancel_job_comfy_prompts(job):
                    job = _commit_video_terminal(
                        job_id, status="failed", stage="failed", error=terminal_error,
                        finished_at=_iso_now(), heartbeat_at=_iso_now(), pid=None, process_group=None,
                    )
                else:
                    request_body = dict(job.get("request") or {})
                    job = _update_video_job(
                        job_id, status="generating", stage="cancel_pending", error="正在核销中断任务所属的Comfy prompt",
                        pending_terminal_status="failed", pending_terminal_stage="failed",
                        pending_terminal_error=terminal_error, heartbeat_at=_iso_now(),
                    )
                    with VIDEO_JOB_LOCK:
                        ACTIVE_VIDEO_JOBS.add(job_id)
                        ACTIVE_VIDEO_SUBJECTS[str(job.get("subject_key") or _video_key(request_body))] = job_id
                    threading.Thread(
                        target=_recover_terminal_video_prompt,
                        args=(job_id, request_body, "failed", "failed", terminal_error),
                        daemon=True, name=f"video-result-recovery-{job_id[:8]}",
                    ).start()
            return self._json(HTTPStatus.OK, job or {"status": "pending"})
        return self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/vision/transcribe":
            length = int(self.headers.get("Content-Length", "0") or 0)
            if length <= 0 or length > 500 * 1024 * 1024:
                return self._json(HTTPStatus.BAD_REQUEST, {"error":"音视频文件大小无效"})
            filename = unquote(self.headers.get("X-Filename", "media.bin")); suffix = Path(filename).suffix or ".bin"
            descriptor, temporary = tempfile.mkstemp(prefix="vision-media-", suffix=suffix)
            source = Path(temporary)
            try:
                with os.fdopen(descriptor, "wb") as stream:
                    remaining = length
                    while remaining:
                        chunk = self.rfile.read(min(1024 * 1024, remaining))
                        if not chunk: raise RuntimeError("音视频上传不完整")
                        stream.write(chunk); remaining -= len(chunk)
                transcript = _transcribe_media(source)
                return self._json(HTTPStatus.OK, {"transcript":transcript or "未检测到可辨识语音"})
            except Exception as error:
                return self._json(HTTPStatus.BAD_GATEWAY, {"error":f"声音识别失败：{str(error)[:500]}"})
            finally:
                source.unlink(missing_ok=True)
        body = self._body()
        if body is None:
            return self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid_json"})
        if (
            parsed.path == "/api/characters/generate"
            and str(body.get("asset_kind") or "").strip() == "scene"
            and str(body.get("asset_phase") or "").strip() == "baseline"
            and not _is_reusable_empty_scene_name(
                body.get("asset_subject") or body.get("name"), _project_character_names(body)
            )
        ):
            return self._json(HTTPStatus.BAD_REQUEST, {"error":"invalid_scene_asset_subject", "detail":"场景资产必须是可复用的纯空地点，不能是人物动作或人物状态"})
        PRODUCTION_REQUEST_SCOPE.identity = _production_identity(body)
        try:
            forwarded = _forward_production_request(parsed.path, body, self.headers.get("X-Production-Dispatched") == "1")
        except Exception as error:
            return self._json(HTTPStatus.SERVICE_UNAVAILABLE, {"error":"workload_dispatch_failed", "message":str(error)})
        if forwarded:
            return self._json(forwarded[0], forwarded[1])
        if parsed.path == "/api/production/run-stage":
            stage = canonical_stage(body.get("stage"))
            try:
                with _claim_production_stage_request(body, stage) as cancel_event:
                    body["_cancel_event"] = cancel_event
                    stage_generation = int(getattr(cancel_event, "lease_generation", 0) or 0)
                    _begin_production_request(body, stage, stage_generation=stage_generation)
                    result = _run_server_production_stage(body)
                    _ensure_production_stage_request_active(cancel_event, stage)
                    workflow = _commit_server_production_stage_result(
                        body, stage, result, cancel_event, stage_generation,
                    )
                return self._json(HTTPStatus.OK, {"result":result, "workflow":workflow})
            except (ProductionLedgerError, ValueError) as error:
                return self._json(HTTPStatus.CONFLICT, {"error":"production_gate_blocked", "message":str(error), "stage":stage})
            except Exception as error:
                cancelled_stage = "cancelled or lease lost" in str(error)
                if stage == "assets" and str(body.get("project_id") or "") and not cancelled_stage:
                    try:
                        _write_project_stage(
                            str(body.get("project_id") or ""), str(body.get("tenant_id") or "local-default"), str(body.get("user_id") or "aoo"), "assets",
                            {"_merge_existing":True, "characters":[], "scenes":[], "props":[], "status":"failed", "error":str(error), "source_episodes":body.get("target_episodes") or [], "census_version":2},
                        )
                    except Exception:
                        pass
                lifecycle = "cancelled" if cancelled_stage else "failed"
                event = locals().get("cancel_event")
                explicit_cancel = bool(getattr(event, "cancel_requested", False))
                # A pure lease loss means a newer generation may already own the
                # stage. The stale owner must not emit any terminal graph event.
                if lifecycle != "cancelled" or explicit_cancel:
                    _production_orchestrator().report(
                        body, stage, lifecycle, error=str(error),
                        stage_generation=int(getattr(event, "lease_generation", 0) or 0),
                        projection_revision=1,
                    )
                return self._json(HTTPStatus.BAD_GATEWAY, {"error":"production_stage_failed", "message":str(error), "stage":stage})
        production_stage = PRODUCTION_ENDPOINT_STAGES.get(parsed.path)
        if production_stage and not _is_asset_subtask_request(parsed.path, body) and self.headers.get("X-Production-Dispatched") != "1":
            try:
                _begin_production_request(body, production_stage)
            except (ProductionLedgerError, ValueError) as error:
                return self._json(HTTPStatus.CONFLICT, {"error":"production_gate_blocked", "message":str(error), "stage":production_stage})
        if parsed.path in {"/api/outline/plan", "/api/outline/episodes", "/api/script/episode", "/api/storyboard", "/api/storyboard/shot"}:
            try:
                body["duration"] = _validated_episode_duration(body.get("duration", 60))
            except ValueError as error:
                return self._json(HTTPStatus.BAD_REQUEST, {"error":"invalid_episode_duration", "message":str(error)})
        scoped_stop_paths = {"/api/generation/stop", "/api/characters/stop", "/api/images/stop", "/api/videos/stop", "/api/tasks/stop"}
        if parsed.path in scoped_stop_paths and not all(str(body.get(key) or "").strip() for key in ("tenant_id", "user_id", "project_id")):
            return self._json(HTTPStatus.BAD_REQUEST, {"ok":False, "error":"invalid_production_scope", "message":"tenant_id, user_id and project_id are required", "stopped":0})
        if parsed.path == "/api/generation/stop" and body.get("stage") in CANONICAL_STAGES:
            stage = canonical_stage(str(body.get("stage")))
            stage_cancelled = _cancel_scoped_production_stage(body, stage)
            if not stage_cancelled:
                return self._json(HTTPStatus.CONFLICT, {"ok":False, "stopped":False, "stage_cancelled":False, "error":"production_stage_not_running", "stage":stage})
            return self._json(HTTPStatus.OK, {"ok":True, "stopped":True, "stage_cancelled":True, "stage":stage})
        if parsed.path == "/api/generation/stop" and body.get("kind") in {"outline", "script"}:
            stage_cancelled = _cancel_scoped_production_stage(body, str(body.get("kind")))
            ok, stopped, error = _stop_text_generation(stage=str(body.get("kind")), project_id=str(body.get("project_id") or ""), client_generation_id=str(body.get("client_generation_id") or ""), requested_job_id=str(body.get("job_id") or ""), identity=body)
            return self._json(HTTPStatus.OK if ok else HTTPStatus.SERVICE_UNAVAILABLE, {"ok":ok, "stopped":stopped, "stage_cancelled":stage_cancelled, **({"error":error} if error else {})})
        if parsed.path == "/api/generation/stop" and body.get("kind") == "storyboard":
            try:
                cancelled = _cancel_production_stage(body, "storyboard")
            except ValueError as error:
                return self._json(HTTPStatus.BAD_REQUEST, {"ok":False, "error":"invalid_production_scope", "message":str(error), "stopped":0})
            persisted = _mark_storyboard_stopped(body)
            return self._json(HTTPStatus.OK, {"ok":True, "stopped":cancelled, "persisted":persisted})
        if parsed.path in {"/api/generation/resume", "/api/generation/stop", "/api/audit/stop"}:
            return self._json(HTTPStatus.OK, {"ok": True})
        if parsed.path == "/api/audit/narrative":
            try:
                return self._json(HTTPStatus.OK, {"audit": _invoke_production_capability("audit.narrative", body=body)})
            except ValueError as error:
                return self._json(HTTPStatus.BAD_REQUEST, {"error":str(error)})
            except Exception as error:
                return self._json(HTTPStatus.BAD_GATEWAY, {"error":f"本地审核模型调用失败：{str(error)[:500]}"})
        if parsed.path == "/api/vision":
            try:
                description = _ollama_vision(list(body.get("images") or []), str(body.get("prompt") or "请识别画面中的人物、场景、动作、文字和关键细节。"))
                return self._json(HTTPStatus.OK, {"description":description})
            except Exception as error:
                return self._json(HTTPStatus.BAD_GATEWAY, {"error":f"视觉识别失败：{str(error)[:500]}"})
        if parsed.path == "/api/assistant/image-plan":
            request_text = str(body.get("message") or "").strip()
            if not request_text:
                return self._json(HTTPStatus.BAD_REQUEST, {"error":"生图需求不能为空"})
            prompt = f"""你是中文生图任务规划器。理解用户自然语言，即使表达口语化、不完整或顺序混乱，也要提取真实意图。
用户原话：{request_text}
输出严格 JSON：{{"count":1,"shared_prompt":"完整保留主体、年龄、外貌、服装、构图、背景、光线、风格、画质和负面约束的中文描述","views":["单张图片的明确视角或构图要求"],"negative_prompt":"禁止内容"}}
规则：
1. 用户要求几张就输出几个 views，count 与 views 长度一致；未说明数量时按明确视角数量，仍无法判断则为1。
2. “正面、背面、侧面、近照、全身”等每个视角必须拆成独立任务，禁止合并为拼图。
3. 不得丢失用户描述，不得自行改变年龄、性别、人物、服装、背景或风格。
4. count 限制1到8。"""
            try:
                plan = _ollama_json(prompt)
                views = [str(value).strip() for value in list(plan.get("views") or []) if str(value).strip()][:8]
                count = max(1, min(8, int(plan.get("count") or len(views) or 1)))
                if not views: views = ["按用户原始要求生成单张独立图片"]
                while len(views) < count: views.append(f"第{len(views) + 1}张独立图片，保持用户要求")
                return self._json(HTTPStatus.OK, {"count":count, "shared_prompt":str(plan.get("shared_prompt") or request_text), "views":views[:count], "negative_prompt":str(plan.get("negative_prompt") or "")})
            except Exception as error:
                return self._json(HTTPStatus.BAD_GATEWAY, {"error":f"生图需求理解失败：{str(error)[:500]}"})
        if parsed.path == "/api/assistant":
            context = body.get("context", {})
            recent = context.get("recent_messages", [])
            message = str(body.get('message', '')).strip()
            explicit_search = body.get("web_search")
            if isinstance(explicit_search, bool):
                search_needed = explicit_search
            else:
                local_context = bool(re.search(r"(?:当前|现在)(?:项目|资源|分镜|任务|剧本|大纲|卡片|页面|生成)", message, re.I))
                explicit_web = bool(re.search(r"(?:联网|网上|全网|搜索|搜一下|查一下|查找|官网|网页|新闻|来源|网址)", message, re.I))
                temporal_web = bool(re.search(r"(?:最新|最近|今天|截至|价格|版本|许可|授权|商用)", message, re.I))
                search_needed = explicit_web or (temporal_web and not local_context)
            sources = []
            search_meta = None
            if search_needed:
                try:
                    search_query = re.sub(r"(?:请|帮我|你帮我)", " ", message, flags=re.I)
                    search_query = re.sub(r"(?:联网搜索|网上搜索|全网搜索|联网查找|搜索|搜一下|查一下|查找)", " ", search_query, flags=re.I)
                    search_query = re.sub(r"(?:给出|附上|提供)?(?:可核验)?(?:来源|链接|网址)[。！？?!]*", " ", search_query, flags=re.I)
                    search_query = re.sub(r"\s+", " ", search_query).strip(" ，。！？?!")
                    translations = (("文生图",'"image generation"'),("图生图",'"image-to-image"'),("视频生成",'"video generation"'),("开源",'"open-source"'),("最新","latest 2026"),("模型","model"),("商用","commercial license"),("苹果芯片",'"Apple Silicon"'),("本地运行","local inference"),("本地部署","local deployment"),("可下载","downloadable weights"),("许可证","license"),("授权","license"))
                    translated_terms = [english for chinese, english in translations if chinese in message]
                    if translated_terms:
                        named_entities = " ".join(re.findall(r"[A-Za-z][A-Za-z0-9._+-]{2,}", message))
                        date_constraints = " ".join(re.findall(r"(?:19|20)\d{2}(?:[-/.年]\d{1,2}(?:[-/.月]\d{1,2}日?)?)?", message))
                        search_query = " ".join(filter(None, (named_entities, date_constraints, *translated_terms, "official release")))
                    if re.search(r"(?:商用|许可|授权)", message, re.I):
                        search_query += " license commercial official GitHub"
                    result_count = 8 if re.search(r"(?:最新|最近|今天|截至)", message, re.I) else 5
                    search_meta = _invoke_production_capability("web.search", body={"query":search_query or message,"count":result_count})
                    sources = list(search_meta.get("results") or [])
                except Exception as error:
                    return self._json(HTTPStatus.BAD_GATEWAY, {"error":f"联网搜索失败，已阻止无来源回答：{str(error)[:500]}","code":"web_search_unavailable"})
                if not sources:
                    return self._json(HTTPStatus.BAD_GATEWAY, {"error":"联网搜索没有返回可核验来源，已阻止无来源回答","code":"web_search_no_results"})
                dated_sources = [item for item in sources if item.get("published_at")]
                if re.search(r"(?:最新|最近|今天|截至)", message, re.I) and dated_sources:
                    lines = ["仅凭“最新”无法安全断言唯一型号；以下是相关来源按发布时间排列的结果，标题没有写明型号时不会自行猜测："]
                    for index, item in enumerate(dated_sources, 1):
                        lines.append(f"{index}. {item['published_at']} — {item['title']}")
                    lines.append("如需确定“最新可下载的开源权重”，还应继续核对候选项目的官方模型卡、发布时间和许可证。")
                    lines.append("\n来源：")
                    lines.extend(f"- {item['title']}：{item['url']}" for item in dated_sources)
                    return self._json(HTTPStatus.OK, {"reply":"\n".join(lines),"intent":"question","sources":dated_sources,"search":{key:search_meta.get(key) for key in ("query","provider_id","searched_at","cache_hit","cache_recovered_at","live_attempts") if key in search_meta}})
            evidence = json.dumps([{"index":index + 1, **item} for index, item in enumerate(sources)], ensure_ascii=False)
            prompt = f"""你是中文短剧制作助手。正常理解并直接回答用户，不虚构已完成操作。
当前项目：{context.get('current_project', '')}
当前资源：{context.get('selected_resource', '')}
近期对话：{json.dumps(recent, ensure_ascii=False)}
用户消息：{message}
联网证据：{evidence}
联网规则：有联网证据时只能依据证据回答时效性事实；不得编造来源；citations只填实际使用的证据index。回答中出现的模型名、产品名、版本号和发布日期必须原样存在于实际引用来源的title、snippet或published_at；“最新”必须比较published_at后再判断，没有足够证据就明确说无法确定。没有联网证据时不要声称查过网络。
输出严格 JSON：{{"reply":"自然、准确、简洁的中文回答","intent":"chat","citations":[1]}}"""
            try:
                result = _ollama_json(prompt)
                reply = str(result.get("reply", "")).strip()
                used = []
                if sources:
                    for value in list(result.get("citations") or []):
                        try: index = int(value) - 1
                        except (TypeError, ValueError): continue
                        if 0 <= index < len(sources) and index not in used: used.append(index)
                    if not used:
                        return self._json(HTTPStatus.BAD_GATEWAY, {"error":"联网回答未提供有效来源引用，已阻止无证据回答","code":"web_search_citations_missing"})
                    reply += "\n\n来源：\n" + "\n".join(f"- {sources[index]['title']}：{sources[index]['url']}" for index in used)
                return self._json(HTTPStatus.OK, {"reply":reply,"intent":result.get("intent", "chat"),"sources":[sources[index] for index in used],"search":({key:search_meta.get(key) for key in ("query","provider_id","searched_at","cache_hit","cache_recovered_at","live_attempts") if key in search_meta} if search_meta else None)})
            except Exception as error:
                return self._json(HTTPStatus.BAD_GATEWAY, {"error": f"本地对话模型调用失败：{error}"})
        if parsed.path == "/api/assistant/agents/run":
            agent = str(body.get("agent", "")).strip()
            task = str(body.get("task", "")).strip()
            if not task:
                return self._json(HTTPStatus.BAD_REQUEST, {"error": "任务内容不能为空"})
            try:
                return self._json(HTTPStatus.OK, _run_system_agent(agent, task, body.get("context", {})))
            except subprocess.TimeoutExpired:
                return self._json(HTTPStatus.GATEWAY_TIMEOUT, {"error": "系统 AI 执行超过30分钟，任务已停止"})
            except (OSError, RuntimeError, ValueError) as error:
                return self._json(HTTPStatus.BAD_GATEWAY, {"error": str(error)})
        if parsed.path == "/api/assistant/agents/start":
            agent = str(body.get("agent", "")).strip(); task = str(body.get("task", "")).strip()
            if agent not in {"main_developer", "software_tester", "inspector"}: return self._json(HTTPStatus.BAD_REQUEST, {"error":"不支持的系统 AI"})
            if not task: return self._json(HTTPStatus.BAD_REQUEST, {"error":"任务内容不能为空"})
            request_id = str(body.get("request_id", "")).strip(); stamp = datetime.now(UTC).isoformat()
            with AGENT_JOB_LOCK:
                store = _load_agent_jobs()
                existing = next((item for item in store.get("jobs", {}).values() if request_id and item.get("request_id") == request_id), None)
                if existing: return self._json(HTTPStatus.OK, {key:existing.get(key) for key in ("job_id", "status", "heartbeat_at")})
                job_id = str(uuid4())
                job = {"job_id":job_id, "request_id":request_id, "agent":agent, "task":task, "context":body.get("context", {}), "status":"queued", "created_at":stamp, "heartbeat_at":stamp}
                store.setdefault("jobs", {})[job_id] = job; _save_agent_jobs(store)
            _start_agent_job(job_id)
            return self._json(HTTPStatus.ACCEPTED, {"job_id":job_id, "status":"queued", "heartbeat_at":stamp})
        if parsed.path == "/api/assistant/route":
            message = str(body.get("message", "")).strip()
            if not message:
                return self._json(HTTPStatus.BAD_REQUEST, {"error": "对话内容不能为空"})
            return self._json(HTTPStatus.OK, _route_system_agent(message, body.get("context", {})))
        if parsed.path == "/api/assistant/history":
            store = _load_assistant(); key = _conversation_key(body.get("context", {}))
            messages = store.get("display_history", {}).get(key)
            if messages is None and len(store.get("display_history", {})) == 1:
                messages = next(iter(store["display_history"].values()))
            return self._json(HTTPStatus.OK, {"messages": messages or []})
        if parsed.path == "/api/assistant/history/save":
            store = _load_assistant(); key = _conversation_key(body.get("context", {}))
            store.setdefault("display_history", {})[key] = body.get("messages", []); _save_assistant(store)
            return self._json(HTTPStatus.OK, {"saved": True})
        if parsed.path == "/api/assistant/draft":
            store = _load_assistant(); key = _conversation_key(body.get("context", {})); action = body.get("action", "read")
            if action == "save":
                content = str(body.get("content", "")); store.setdefault("drafts", {})[key] = {"content": content}; _save_assistant(store)
            return self._json(HTTPStatus.OK, {"draft": store.get("drafts", {}).get(key)})
        if parsed.path == "/api/assistant/sessions":
            store = _load_assistant(); context = body.get("context", {}); session_id = body.get("session_id") or str(uuid4())
            session = {"session_id": session_id, "tenant_id": context.get("tenant_id", "local-default"), "user_id": context.get("user_id", "aoo"), "title": "新对话", "archived": False, "created_at": int(datetime.now(UTC).timestamp() * 1000), "updated_at": int(datetime.now(UTC).timestamp() * 1000)}
            store.setdefault("sessions", {})[f"{session['tenant_id']}:{session['user_id']}:{session_id}"] = session; _save_assistant(store)
            return self._json(HTTPStatus.OK, {"sessions": [session], "session": session})
        if parsed.path == "/api/outline/plan":
            job_id, conflict = _begin_text_job(body, "outline", "plan", OUTLINE_JOB_TIMEOUT_SECONDS, "/api/outline/plan")
            if conflict:
                return self._json(HTTPStatus.CONFLICT, {"error":"该项目大纲已有真实运行任务", "active_job":conflict})
            prompt = f"""你是专业中文短剧策划。根据以下要求输出严格 JSON，不要输出解释。
必须执行的全流程规范：
{_production_spec_for('outline')}

题材：{body.get('topic', '')}
风格：{body.get('style', '')}
语言：{body.get('language', '简体中文')}
集数：{body.get('episode_count', 1)}
每集时长：{body.get('duration', 60)}秒
大纲必须在剧名之后、分集剧情之前提供“核心人物简介”，收录预计出场不少于2次的角色，固定为“姓名｜岗位标签｜性格特质｜核心目标”。都市逆袭类必须且仅设1名男主、1名女主；兼任职能使用“女主/盟友”等双标签，其他岗位不得顶替。正派禁用贬义性格词，反派可用。
JSON 格式：{{"title":"剧名","general_outline":"完整故事总纲","characters":[{{"name":"姓名","identity":"男主/女主/盟友/反派或双标签","personality":"符合人物立场的稳定性格特质","core_motivation":"核心目标","appearance_count":2}}],"arcs":[{{"name":"故事线名称","summary":"故事线说明"}}]}}
            必须贴合用户题材，不得改成其他时代或类型。"""
            try:
                plan = _ollama_json(prompt, TEXT_FORMAL_MODEL, TEXT_FORMAL_ESTIMATED_MEMORY,
                    release_model=False, keep_alive=300, timeout_seconds=OUTLINE_JOB_TIMEOUT_SECONDS,
                    owner_job_id=job_id)
                _finish_text_job(job_id, "completed")
                if _text_job_stopped(job_id):
                    return self._json(HTTPStatus.CONFLICT, {"error":"大纲任务已停止", "job_id":job_id})
                return self._json(HTTPStatus.OK, {"plan": plan, "job_id":job_id})
            except Exception as error:
                _finish_text_job(job_id, "failed", str(error)[:500])
                return self._json(HTTPStatus.BAD_GATEWAY, {"error": f"本地大纲模型调用失败：{error}"})
        if parsed.path == "/api/outline/episodes":
            start = max(1, int(body.get("start_episode", 1)))
            count = max(1, int(body.get("count", 1)))
            total_episodes = max(count, int(body.get("total_episodes", count)))
            job_id, conflict = _begin_text_job(body, "outline", f"episodes:{start}-{start + count - 1}", OUTLINE_JOB_TIMEOUT_SECONDS, "/api/outline/episodes")
            if conflict:
                return self._json(HTTPStatus.CONFLICT, {"error":"该项目大纲已有真实运行任务", "active_job":conflict})
            previous_episodes = body.get("previous_episodes") if isinstance(body.get("previous_episodes"), list) else []
            prompt = f"""你是专业中文短剧编剧。根据总纲生成第 {start} 集起连续 {count} 集的分集梗概，输出严格 JSON，不要解释。
必须执行的全流程规范：
{_production_spec_for('outline')}

总纲：{json.dumps(body.get('plan', {}), ensure_ascii=False)}
已生成分集与全剧状态：{json.dumps(previous_episodes, ensure_ascii=False)}
用户题材：{body.get('topic', '')}
总集数：{body.get('total_episodes', count)}；每集时长：{body.get('duration', 60)}秒；风格：{body.get('style', '')}
每集必须让女主主动决策或主动反击；男主、盟友和宗门群像不得连续复用救场职能；反派手段必须升级并承担新的失败代价。
每集只允许推进一项明确的祥瑞能力并写清能力代价；每2至3集必须出现一次符合剧名卖点的全宗门护宠名场面。
cliffhanger 必须是能直接拍出来的身份信物、致命咒术、亲缘反转、道具异变或敌人现身，禁止“阴谋仍在、威胁逼近、真相将揭晓”等空泛表述。
JSON 格式：{{"episodes":[{{"episode":{start},"title":"全剧唯一标题","story_stage":"第{start}集·当前单向剧情阶段","core_event":"全剧唯一核心事件","protagonist_action":"女主本集主动决策或主动反击","ability_progression":"本集新增能力、使用方式与代价","villain_action":"本集差异化反派手段及失败代价","supporting_motivation":"男主或盟友自身动机推进","protection_set_piece":"本集全宗门护宠具体场面或本集为何不设置","irreversible_change":"本集全剧唯一且不可恢复的状态变化","new_information":"本集新揭示的碎片线索","resolved_setup":"本集回收伏笔或明确写无","cliffhanger":"下一集可见、具象、不可逆的明确悬念","synopsis":"包含开端、冲突、反转、结尾钩子的完整梗概"}}]}}
            episodes 必须正好 {count} 项，episode 从 {start} 连续编号。"""
            try:
                episodes = _validate_outline_episode_batch(
                    _ollama_json(prompt, TEXT_FORMAL_MODEL, TEXT_FORMAL_ESTIMATED_MEMORY,
                        release_model=start + count - 1 >= total_episodes, keep_alive=300,
                        timeout_seconds=OUTLINE_JOB_TIMEOUT_SECONDS, owner_job_id=job_id).get("episodes", []),
                    start,
                    count,
                    previous_episodes,
                )
                _finish_text_job(job_id, "completed")
                if _text_job_stopped(job_id):
                    return self._json(HTTPStatus.CONFLICT, {"error":"大纲任务已停止", "job_id":job_id})
                return self._json(HTTPStatus.OK, {"episodes": episodes, "job_id":job_id})
            except Exception as error:
                _unload_ollama_model(TEXT_FORMAL_MODEL)
                _finish_text_job(job_id, "failed", str(error)[:500])
                return self._json(HTTPStatus.BAD_GATEWAY, {"error": f"本地分集模型调用失败：{error}"})
        if parsed.path == "/api/script/episode":
            episode_outline = body.get("episode_outline") or {}
            episode = int(episode_outline.get("episode") or body.get("episode") or 1)
            target_duration = int(body.get("duration", 60))
            project_id = str(body.get("project_id") or "")
            requested_id = str(body.get("generation_id") or "")
            job_id = str(uuid4())
            with TEXT_JOB_LOCK:
                conflict = next((active_id for active_id, active in ACTIVE_TEXT_JOBS.items() if active.get("project_id") == project_id and active.get("episode") == episode), "")
                if conflict:
                    return self._json(HTTPStatus.CONFLICT, {"error":"script_generation_active", "active_job":conflict})
                stamp = _iso_now()
                ACTIVE_TEXT_JOBS[job_id] = {
                    "project_id":project_id, "episode":episode, "heartbeat_epoch":time.time(), "started_epoch":time.time(),
                    "thread_id":threading.get_ident(), "worker_thread":threading.current_thread(),
                }
                _update_text_job(job_id, job_id=job_id, client_generation_id=requested_id, project_id=project_id, episode=episode,
                                 stage="script", phase=f"episode:{episode}", endpoint="/api/script/episode", request=dict(body),
                                 status="generating", started_at=stamp, heartbeat_at=stamp, error="")
            heartbeat_stop = threading.Event()
            def heartbeat() -> None:
                while not heartbeat_stop.wait(2):
                    with TEXT_JOB_LOCK:
                        active = ACTIVE_TEXT_JOBS.get(job_id)
                        if not active: return
                        active["heartbeat_epoch"] = time.time()
                        _update_text_job(job_id, heartbeat_at=_iso_now())
            threading.Thread(target=heartbeat, daemon=True, name=f"script-heartbeat-{job_id[:8]}").start()
            prompt = f"""你是专业中文竖屏短剧编剧。为第 {episode} 集写完整可拍摄剧本，严格输出 JSON，不要解释。
必须执行的全流程规范：
{_production_spec_for('script')}

全剧总纲：{body.get('general_outline', '')}
项目题材：{body.get('topic', '')}
本集梗概：{json.dumps(episode_outline, ensure_ascii=False)}
上一集梗概：{json.dumps(body.get('previous_outline'), ensure_ascii=False)}
下一集梗概：{json.dumps(body.get('next_outline'), ensure_ascii=False)}
全剧分集状态表：{json.dumps(body.get('all_episode_outlines', []), ensure_ascii=False)}
此前已完成剧本摘要：{json.dumps(body.get('previous_scripts', []), ensure_ascii=False)}
角色档案：{json.dumps(body.get('characters', []), ensure_ascii=False)}
目标时长：{target_duration}秒；画幅：{body.get('aspect', '9:16')}；风格：{body.get('style', '')}
补充要求：{body.get('retry_requirement', '')}
本集必须落实分集状态表中的女主主动行动、能力升级及代价、配角自身动机、反派差异化手段、宗门护宠场面和具象钩子；禁止复用此前剧本的冲突流程。
content 必须为12-20个剧情段落组成的 JSON 数组，每段分别包含“画面、动作、台词、旁白、情绪”；台词与旁白必须分开。段落数量必须足以覆盖目标时长。
段落时长必须根据对白量、动作复杂度、冲突和钩子所需停留时间分配，禁止全部5秒、禁止等长切分、禁止固定模板节奏。后端会统一生成连续时间段，总和必须严格等于{target_duration}秒。
JSON 格式：{{"script":{{"episode":{episode},"title":"本集标题","content":[{{"画面":"...","动作":"...","台词":"...或无","旁白":"...或无","情绪":"..."}}]}}}}"""
            try:
                result = _ollama_json(prompt, TEXT_FORMAL_MODEL, TEXT_FORMAL_ESTIMATED_MEMORY, owner_job_id=job_id); script = result.get("script", result)
                script["episode"] = episode
                script["target_duration"] = target_duration
                timed_content = _allocate_script_timing(script.get("content", ""), target_duration)
                script["content"] = _human_readable_script_content(timed_content)
                _validate_script_timing(script["content"], target_duration)
                with TEXT_JOB_LOCK:
                    current = _load_text_jobs().get("jobs", {}).get(job_id, {})
                    if current.get("status") == "failed":
                        return self._json(HTTPStatus.CONFLICT, {"error":current.get("error") or "剧本任务已停止", "job_id":job_id})
                    _finish_text_job(job_id, "completed")
                return self._json(HTTPStatus.OK, {"script": script, "job_id":job_id})
            except Exception as error:
                _finish_text_job(job_id, "failed", str(error)[:500])
                return self._json(HTTPStatus.BAD_GATEWAY, {"error": f"本地剧本模型调用失败：{error}"})
            finally:
                heartbeat_stop.set()
        if parsed.path == "/api/storyboard/shot":
            episode = max(1, int(body.get("episode", 1)))
            shot_number = max(1, int(body.get("shot_number", 1)))
            shot_count = max(1, int(body.get("shot_count", 15)))
            start_second = float(body.get("start_second", 0))
            end_second = float(body.get("end_second", start_second + 4))
            prompt = f"""你是专业短剧分镜师。只生成第 {episode} 集的第 {shot_number}/{shot_count} 个镜头，严格输出 JSON，不要解释。
必须执行的全流程规范：
{_production_spec_for('storyboard')}

完整剧本：{body.get('script', '')}
项目题材：{body.get('topic', '')}；风格：{body.get('style', '')}
本镜头时间：{start_second:g}-{end_second:g}秒。
上一镜头：{json.dumps(body.get('previous_shot'), ensure_ascii=False)}
已生成镜头摘要：{json.dumps(body.get('generated_summaries', []), ensure_ascii=False)}
本镜头必须完成的剧情推进：{body.get('story_progress', '')}
补充要求：{body.get('retry_requirement', '')}
必须承接上一镜头并推进新的剧情信息，禁止重复画面或动作；对白必须取自剧本对应进度。
生成前必须逐条对照“已生成镜头摘要”：本镜头的场景构图、人物状态、核心动作、动作结果和叙事信息至少有一项形成明确推进；禁止仅替换近义词、景别或情绪来伪装新镜头。若原剧本当前段信息不足，必须把连续动作拆成新的动作阶段，不得复制上一阶段。
JSON 格式：{{"shot":{{"scene":"场景","shot_size":"景别","camera":"机位与运动","visual":"画面","action":"动作","dialogue":"台词或旁白，无则填无","sound":"声音","emotion":"情绪","image_prompt":"完整中文生图提示词","shot_type":"action"}}}}"""
            try:
                result = _ollama_json(prompt, TEXT_FORMAL_MODEL, TEXT_FORMAL_ESTIMATED_MEMORY); shot = result.get("shot", result)
                if not isinstance(shot, dict): raise ValueError("镜头结果不是对象")
                for field in ("scene", "shot_size", "camera", "visual", "action", "sound", "image_prompt"):
                    if not str(shot.get(field, "")).strip(): raise ValueError(f"镜头缺少字段：{field}")
                shot.update({"episode":episode, "shot_number":shot_number, "start_second":start_second, "end_second":end_second})
                shot.setdefault("dialogue", "无"); shot.setdefault("emotion", "自然"); shot.setdefault("shot_type", "action")
                return self._json(HTTPStatus.OK, {"shot":shot})
            except Exception as error:
                return self._json(HTTPStatus.BAD_GATEWAY, {"error":f"本地分镜镜头模型调用失败：{error}"})
        if parsed.path == "/api/storyboard":
            episode = max(1, int(body.get("episode", 1)))
            base_prompt = f"""你是专业短剧导演。只制定第 {episode} 集的紧凑视觉导演方案，严格输出 JSON，不要解释。
必须执行的全流程规范：
{_production_spec_for('storyboard')}

项目题材：{body.get('topic', '')}
目标时长：{body.get('duration', 60)}秒；画幅：{body.get('aspect', '9:16')}；风格：{body.get('style', '')}
角色档案：{json.dumps(body.get('characters', []), ensure_ascii=False)}
补充要求：{body.get('retry_requirement', '')}
只返回统一色彩、固定主光和4条安全运镜规则；运镜必须少、慢、稳，禁止旋转、晃动和变速。
JSON 格式：{{"direction":{{"palette":"≤24字","lighting":"≤24字","camera_rules":["≤16字","≤16字","≤16字","≤16字"]}}}}"""
            try:
                result = _ollama_json(
                    base_prompt, TEXT_FORMAL_MODEL, TEXT_FORMAL_ESTIMATED_MEMORY,
                    num_ctx=4096, num_predict=512, timeout_seconds=240,
                )
                direction = result.get("direction", result)
                if not isinstance(direction, dict):
                    raise ValueError("视觉导演方案不是对象")
                shots = _compile_storyboard_from_script(body.get("script", ""), episode, str(body.get("style") or ""), direction, body.get("characters", []))
                shots = _validate_storyboard(shots, float(body.get("duration", 60)), body.get("script", ""))
                return self._json(HTTPStatus.OK, {"storyboard": {"episode": episode, "shots": shots}, "direction": direction})
            except Exception as error:
                return self._json(HTTPStatus.BAD_GATEWAY, {"error": f"本地分镜模型调用失败：{error}"})
        if parsed.path == "/api/characters/extract":
            target_episodes = [int(value) for value in body.get("target_episodes", []) if str(value).isdigit()]
            required_characters = [str(value).strip() for value in body.get("required_characters", []) if str(value).strip()]
            prompt = f"""你是短剧美术资产统筹。只根据指定集数文本提取去重后的人物、场景、道具，输出严格 JSON，不要解释。
必须执行的全流程规范：
{_production_spec_for('assets')}

指定集数：{target_episodes or '当前输入范围'}
大纲：{body.get('outline', '')}
剧本：{body.get('scripts', '')}
画面风格：{body.get('style', '')}
人物提取硬性规则：characters 必须包含本集实际出场人物 {required_characters}，姓名完全一致；不得加入只在其他集出现的人物。
场景提取硬性规则：按可复用的实体地点归并，内外空间必须分开；scene.name只能是地点或空间名称，严禁人物姓名、人物动作、姿态、状态或剧情句子；动作、人物状态、光晕变化不得另算场景。场景image_prompt只能描述空间、建筑、固定陈设和光线，人物数量严格为零。
道具提取硬性规则：只保留本集由人物持有、使用或推动剧情的可独立绘制实体；树木、花草、山景属于场景环境，金光、光晕、符文光效属于特效。服装是独立道具资产，剧本或分镜出现的日常服、战斗服、礼服、长袍、披风等必须进入props，category固定为“服装”，asset_type固定为“costume”，owner必须指向角色名，并提供稳定costume_id、costume_version、tags；禁止把服装并入人物本体。
服装基准图固定为45度三分之二完整展示图，清楚展示正面、顶面/肩部结构与侧面层次，纯中性背景、无人、无人体模型、无文字；确认后按道具3D链进入TripoSR和Blender。
每项必须给出出现集数 episodes；只输出指定集数范围内的完整清单，不得用全剧其他集补足。
JSON 格式：{{"characters":[{{"name":"人物名","role":"男主角/女主角/配角/反派","gender":"男性/女性","image_prompt":"年龄、性别、五官、发型、体态和电影画面风格；服装只引用costume_id","status":"pending"}}],"scenes":[{{"name":"场景名","location":"地点","period":"时间","first_episode":1,"episodes":[1],"layout":"空间布局","lighting":"光线","fixed_elements":[],"continuity_rules":"连续性规则","image_prompt":"空间、时间、光线、陈设和电影画面风格，无人物","status":"pending"}}],"props":[{{"name":"道具或服装名","category":"类别或服装","asset_type":"prop或costume","owner":"持有人","costume_id":"服装稳定ID，普通道具留空","costume_version":"v1","tags":[],"first_episode":1,"episodes":[1],"appearance":"外观","continuity_rules":"连续性规则","image_prompt":"材质、形状、颜色和使用痕迹，45度三分之二，中性背景，无人物","status":"pending"}}]}}"""
            try:
                try:
                    result = _ollama_json(prompt)
                except (json.JSONDecodeError, ValueError) as first_error:
                    result = _ollama_json(
                        prompt
                        + "\n上一次输出不是可解析的完整JSON（"
                        + str(first_error)[:240]
                        + "）。只重试一次：必须关闭所有引号、数组和对象，不要截断，不要输出Markdown。"
                    )
                characters = [item for item in result.get("characters", []) if isinstance(item, dict) and str(item.get("name", "")).strip()]
                by_name = {str(item.get("name", "")).strip(): item for item in characters}
                for name in required_characters:
                    by_name.setdefault(name, {"name":name, "role":"核心角色", "gender":"", "image_prompt":f"{name}，中国人，自然东亚面孔，中国影视角色", "status":"pending"})
                invalid_prop_tokens = ("金光", "光晕", "光效", "特效", "树木", "花草", "山景", "树林")
                props = [item for item in result.get("props", []) if isinstance(item, dict) and str(item.get("name", "")).strip() and not any(token in str(item.get("name", "")) for token in invalid_prop_tokens)]
                for item in props:
                    costume_text = " ".join(str(item.get(field) or "") for field in ("name", "category", "asset_type", "appearance", "image_prompt"))
                    is_costume = str(item.get("category") or "") == "服装" or str(item.get("asset_type") or "") == "costume" or any(
                        token in costume_text for token in ("衣服", "服装", "日常服", "战斗服", "练功服", "常服", "华服", "长袍", "衣袍", "战甲", "礼服", "披风", "斗篷", "裙", "衫", "外衣", "制服")
                    )
                    if is_costume:
                        item["category"] = "服装"; item["asset_type"] = "costume"
                        owner = str(item.get("owner") or "").strip()
                        if not owner and len(required_characters) == 1:
                            owner = required_characters[0]
                        if not owner:
                            raise ValueError(f"服装资产“{item.get('name')}”缺少明确owner，禁止作为无主服装入库")
                        if required_characters and owner not in required_characters:
                            raise ValueError(f"服装资产“{item.get('name')}”owner不在当前出镜角色范围")
                        item["owner"] = owner
                        item["costume_id"] = str(item.get("costume_id") or _costume_id(str(item.get("owner") or item.get("name") or "costume"), str(item.get("name") or "daily")))
                        item["costume_version"] = str(item.get("costume_version") or "v1")
                        item["tags"] = [str(value) for value in item.get("tags", []) if str(value).strip()]
                scripted_costumes = re.findall(r"([\w\u4e00-\u9fff]+)=(costume_[\w-]+)@(v\d+)", str(body.get("scripts") or ""))
                known_costume_ids = {str(item.get("costume_id") or "") for item in props if str(item.get("asset_type") or "") == "costume"}
                for owner, costume_id, costume_version in scripted_costumes:
                    if costume_id in known_costume_ids:
                        continue
                    if required_characters and owner not in required_characters:
                        raise ValueError(f"分镜服装{costume_id}的owner不在当前出镜角色范围")
                    label = costume_id.rsplit("_", 1)[-1]
                    props.append({
                        "name":f"{owner}-{label}服装", "category":"服装", "asset_type":"costume", "owner":owner,
                        "costume_id":costume_id, "costume_version":costume_version, "tags":[label],
                        "first_episode":min(target_episodes or [1]), "episodes":target_episodes or [1],
                        "appearance":f"{owner}在分镜中指定的{label}服装",
                        "continuity_rules":f"仅在分镜引用{costume_id}@{costume_version}时使用",
                        "image_prompt":f"{owner}的{label}服装，单件完整服装45度三分之二展示，纯中性背景，无人物",
                        "status":"pending",
                    })
                    known_costume_ids.add(costume_id)
                scenes = _normalize_empty_scene_assets(result.get("scenes", []), required_characters)
                return self._json(HTTPStatus.OK, {"characters":list(by_name.values()), "scenes":scenes, "props":props, "census":{"episodes":target_episodes,"characters":len(by_name),"scenes":len(scenes),"props":len(props)}})
            except Exception as error:
                return self._json(HTTPStatus.BAD_GATEWAY, {"error": f"本地资产模型调用失败：{error}"})
        if parsed.path == "/api/assets/3d/generate":
            project_id = str(body.get("project_id") or "")
            kind = str(body.get("asset_kind") or "")
            asset_name = str(body.get("asset_name") or body.get("name") or "")
            if not project_id or not asset_name or kind not in {"character", "prop", "scene"}:
                return self._json(HTTPStatus.BAD_REQUEST, {"error":"project_id、asset_name、asset_kind不能为空"})
            job_id = str(uuid4())
            subject_key = f"{project_id}:3d:{kind}:{asset_name}"
            _cleanup_invalid_image_tasks()
            with IMAGE_JOB_LOCK:
                active_job_id = ACTIVE_IMAGE_SUBJECTS.get(subject_key)
                if active_job_id:
                    return self._json(HTTPStatus.CONFLICT, {"error":"该资产3D任务正在运行", "active_job":active_job_id})
                ACTIVE_IMAGE_SUBJECTS[subject_key] = job_id
                ACTIVE_IMAGE_JOBS.add(job_id)
                store = _load_image_jobs()
                store.setdefault("jobs", {})[job_id] = {
                    "job_id":job_id, "request_name":asset_name, "subject_key":subject_key, "workflow":"asset_3d",
                    "endpoint":"/api/assets/3d/generate", "request":dict(body),
                    "project_id":project_id, "asset_kind":kind, "asset_name":asset_name, "status":"queued", "phase":"queued",
                    "asset_type":str(body.get("asset_type") or kind),
                    "costume_id":str(body.get("costume_id") or ""),
                    "started_at":_iso_now(), "heartbeat_at":_iso_now(), "timeout_seconds":IMAGE_TASK_TIMEOUT_SECONDS,
                    "queue_timeout_seconds":IMAGE_QUEUE_TIMEOUT_SECONDS, "retry_count":0, "pid":None, "process_group":None,
                }
                _save_image_jobs(store)
            worker = threading.Thread(target=_execute_asset_3d_job, args=(dict(body), job_id, subject_key),
                                      daemon=True, name=f"asset-3d-{job_id[:8]}")
            worker.start()
            return self._json(HTTPStatus.ACCEPTED, {"job_id":job_id, "status":"queued", "phase":"queued"})
        if parsed.path == "/api/assets/3d/confirm":
            try:
                return self._json(HTTPStatus.OK, _confirm_asset_3d_job(body))
            except ValueError as error:
                return self._json(HTTPStatus.CONFLICT, {"error":str(error)})
        if parsed.path == "/api/assets/purge-generated":
            try:
                result = _purge_generated_assets(body.get("project_id"), body.get("asset_kind"), body.get("asset_name"))
                return self._json(HTTPStatus.OK, {"purged": True, **result})
            except ValueError as error:
                return self._json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
            except OSError as error:
                return self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": f"旧资产清理失败：{error}"})
        if parsed.path == "/api/poses/extract":
            try:
                with _claim_production_resource("image", f"pose-{uuid4()}", timeout=IMAGE_QUEUE_TIMEOUT_SECONDS):
                    _require_memory(10 * GIB); pose = _invoke_production_capability("pose.extract", name=body.get("name") or f"pose_{uuid4().hex[:8]}", reference_url=str(body.get("image_url", "")))
                return self._json(HTTPStatus.OK, {"pose":pose})
            except Exception as error:
                return self._json(HTTPStatus.BAD_GATEWAY, {"error":f"OpenPose 骨骼提取失败：{str(error)[:500]}"})
        if parsed.path in {"/api/characters/generate", "/api/shots/generate", "/api/shots/repair", "/api/assistant/images/generate"}:
            shot_characters = body.get("characters", [])
            if parsed.path in {"/api/shots/generate", "/api/shots/repair"} and isinstance(shot_characters, list) and any(
                isinstance(character, dict) and str(character.get("change_type") or "") == "change" for character in shot_characters
            ):
                return self._json(HTTPStatus.NOT_IMPLEMENTED, {
                    "error":"capability_not_implemented",
                    "detail":"独立服装角色基础体穿衣、蒙皮与碰撞链尚未完成，换装镜头已在服务端阻断",
                })
            name = body.get("name") or f"shot_{body.get('episode', 0)}_{body.get('shot_number', 0)}"
            request_name = str(name)
            job_id = str(uuid4())
            is_character_generation = parsed.path == "/api/characters/generate"
            requested_kind = str(body.get("asset_kind", "")).strip()
            requested_phase = str(body.get("asset_phase", "")).strip()
            if requested_kind in {"scene", "prop"} and requested_phase == "variant":
                return self._json(HTTPStatus.BAD_REQUEST, {"error":"asset_2d_variants_disabled_for_3d_asset", "asset_kind":requested_kind})
            if requested_kind == "scene" and requested_phase == "baseline" and not _is_reusable_empty_scene_name(
                body.get("asset_subject") or name, _project_character_names(body)
            ):
                return self._json(HTTPStatus.BAD_REQUEST, {"error":"invalid_scene_asset_subject", "detail":"场景资产必须是可复用的纯空地点，不能是人物动作或人物状态"})
            subject_key = ":".join(str(value or "") for value in (body.get("project_id"), body.get("asset_kind"), body.get("asset_subject") or name))
            _cleanup_invalid_image_tasks()
            with IMAGE_JOB_LOCK:
                active_job_id = ACTIVE_IMAGE_SUBJECTS.get(subject_key)
                if active_job_id:
                    active_job = _load_image_jobs().get("jobs", {}).get(active_job_id, {})
                    return self._json(HTTPStatus.CONFLICT, {"error":f"该资产正在生成：{body.get('asset_subject') or '当前图片'}", "active_job":active_job.get("request_name") or request_name})
                ACTIVE_IMAGE_SUBJECTS[subject_key] = job_id
                jobs = _load_image_jobs()
                jobs.setdefault("jobs", {})[job_id] = {
                    "job_id":job_id, "request_name":request_name, "subject_key":subject_key, "endpoint":parsed.path, "request":dict(body), "status":"queued", "started_at":_iso_now(),
                    "project_id":str(body.get("project_id") or ""),
                    "heartbeat_at":_iso_now(), "timeout_seconds":IMAGE_TASK_TIMEOUT_SECONDS,
                    "queue_timeout_seconds":IMAGE_QUEUE_TIMEOUT_SECONDS, "retry_count":0, "pid":None, "process_group":None,
                }
                _save_image_jobs(jobs)
                ACTIVE_IMAGE_JOBS.add(job_id)
                ACTIVE_IMAGE_WORKERS[job_id] = threading.current_thread()
            try:
                references = body.get("references") or []
                base_image_prompt = str(body.get("prompt", "")).strip()
                asset_kind = str(body.get("asset_kind", "")).strip()
                asset_phase = str(body.get("asset_phase", "")).strip()
                if references and asset_phase == "variant":
                    current_url = str(references[0].get("url", "")) if isinstance(references[0], dict) else ""
                    try:
                        _reference_path(current_url)
                    except Exception:
                        recovered_url = _latest_completed_asset_image_url(body.get("project_id"), asset_kind, body.get("asset_subject"))
                        if not recovered_url:
                            raise RuntimeError("已确认基准图文件已失效，请重新生成基准图")
                        references = [dict(references[0], url=recovered_url), *references[1:]]
                        body["references"] = references
                        clothing_url = str(body.get("clothing_reference_url") or "")
                        try:
                            _reference_path(clothing_url)
                        except Exception:
                            body["clothing_reference_url"] = recovered_url
                required_text = _required_image_text(body, base_image_prompt) if asset_kind == "scene" or parsed.path in {"/api/shots/generate", "/api/shots/repair", "/api/assistant/images/generate"} else ""
                base_image_prompt = _blank_requested_text(base_image_prompt, required_text)
                if parsed.path == "/api/characters/generate" and asset_kind == "character" and asset_phase == "baseline":
                    identity_description = str(body.get("identity_prompt", "")).strip() or base_image_prompt
                    identity_description = re.sub(
                        r"(?:单人物\s*)?(?:(?:0\s*(?:°|度)\s*)?正面|左\s*45\s*(?:°|度)?|右\s*45\s*(?:°|度)?|90\s*(?:°|度)?\s*侧面|侧面\s*90\s*(?:°|度)?|180\s*(?:°|度)?\s*背面|背面\s*180\s*(?:°|度)?)\s*(?:完整\s*)?(?:近照|半身\s*(?:照)?|全身\s*(?:照|视图)?|视图)?",
                        "", identity_description,
                    )
                    identity_description = re.sub(
                        r"(?:单人物\s*)?(?:完整\s*)?(?:近照|半身\s*照|全身\s*(?:照|视图)|多角度\s*视图)", "", identity_description,
                    )
                    identity_description = re.sub(r"，{2,}", "，", identity_description).strip("，。；、 ")
                    flux_identity = _flux_identity_prompt(identity_description)
                    base_image_prompt = (
                        f"PRIMARY SUBJECT: {flux_identity}.\n"
                        "A single centered full-body identity and 3D-reconstruction reference at exact zero-degree front view, eye-level camera and neutral expression. "
                        "The face, shoulders, chest, pelvis, knees and both feet must be square to the camera; face yaw and roll must be near zero. "
                        "The complete hairstyle, head, both relaxed hands, garment layers, legs and both shoes must be visible with safe margins from head to feet. "
                        "Neutral standing A-pose, natural human proportions, specified traditional garment colors and accessories fully visible. "
                        "Flat solid neutral gray studio background. No scenery, props, extra people, duplicated person, collage, panels, labels, letters, Chinese characters, "
                        "numbers, arrows, captions, stamps, logos, border or watermark. No crop, sitting, dynamic action, left or right three-quarter view, profile, back view, close-up or half-body framing."
                    )
                if parsed.path == "/api/characters/generate" and asset_kind == "scene":
                    base_image_prompt = (
                        "最高优先级硬性限制：这是纯空场景建筑与环境参考图，画面中人物数量必须严格等于零。"
                        "禁止真人、人物、人体、人体局部、手脚、剪影、背影、倒影中的人、镜中人、照片人物、海报人物、"
                        "屏幕人物、雕像人形、人群和任何人形主体；只展示空间、建筑、家具、陈设、自然环境与光线。\n"
                        f"场景描述：{base_image_prompt}"
                    )
                if parsed.path == "/api/characters/generate" and asset_kind == "prop":
                    base_image_prompt = _sanitize_no_text_asset_prompt(base_image_prompt)
                    sculpture_subject = any(token in base_image_prompt for token in ("雕像", "雕塑", "人偶", "玩偶"))
                    base_image_prompt = (
                        "最高优先级硬性限制：这是单个独立道具资产图，画面中真人和真实人体数量必须严格等于零。"
                        "禁止真人、真实人体、真人手脚、真人背影、真人剪影、真人倒影、镜中真人、照片人物、海报人物、"
                        "屏幕人物和人群；禁止用真人手持、佩戴、展示或操作道具。"
                        "必须采用电商产品摄影构图：只允许一个道具本体居中完整悬置或平放，占画面主要区域；背景只能是无缝纯中性灰。"
                        "禁止室内外环境、建筑、房间、商店、街道、门窗、家具、柜台、山水、花木、地面延伸、招牌、海报、文字和其他物体。"
                        f"{'当前道具本身是雕像、雕塑、人偶或玩偶，允许该非真人主体完整出现，但禁止出现制作或展示它的真人。' if sculpture_subject else '雕像、雕塑或人偶不得作为陪衬主体出现。'}\n"
                        f"道具描述：{base_image_prompt}"
                    )
                human_face_rule = "人物默认必须为中国人、自然东亚面孔、中国影视角色；禁止欧美面孔和混血面孔。" if any(token in base_image_prompt for token in ("人物", "男性", "女性", "男人", "女人", "男主", "女主", "角色", "人像")) else ""
                schnell_baseline = parsed.path == "/api/characters/generate" and asset_phase == "baseline"
                selected_lora = None if schnell_baseline or references else _automatic_lora(body, base_image_prompt)
                if parsed.path == "/api/characters/generate" and asset_kind == "prop":
                    prop_subject = str(body.get("asset_subject") or name).split(":", 1)[0]
                    prop_english = (
                        "one pale cyan carved jade pendant with a smooth polished surface and subtle ancient engraved motifs"
                        if "玉佩" in prop_subject or "玉佩" in base_image_prompt else f"one isolated {prop_subject} prop"
                    )
                    indexed_prompt = (
                        f"STRICT STUDIO PRODUCT PHOTOGRAPH. The only visible object is {prop_english}. "
                        "Exactly one small portable prop centered and fully visible, front view, seamless flat neutral gray background, soft even product lighting. "
                        "Empty background. No room, no shop, no street, no building, no landscape, no furniture, no display stand, no sign, no letters, "
                        "no text, no logo, no poster, no person, no hand, no body, no additional object. "
                        f"Object specification: {base_image_prompt}"
                    )[:1800]
                else:
                    indexed_prompt = (f"{base_image_prompt}\n{human_face_rule}竖屏短剧电影资产图；主体身份、服装、材质、颜色和空间结构必须稳定；"
                                      "构图清晰，真实光影，无文字、无水印、无重复主体、无畸形。")[:1800]
                if parsed.path in {"/api/shots/generate", "/api/shots/repair"} and references:
                    image = _invoke_production_capability("image.shot.multireference", name=name, prompt=indexed_prompt, width=body.get("width"), height=body.get("height"), references=references, job_id=job_id)
                elif parsed.path == "/api/characters/generate" and references and asset_phase == "repair":
                    reference_url = str(references[0].get("url", ""))
                    source = _reference_path(reference_url)
                    target = OUTPUT_ROOT / "images" / f"{_safe_name(name)}.png"
                    width_value = max(512, min(1024, int(body.get("width") or 928))) // 16 * 16
                    height_value = max(512, min(1664, int(body.get("height") or 1664))) // 16 * 16
                    with _claim_production_resource("image", job_id, timeout=IMAGE_QUEUE_TIMEOUT_SECONDS):
                        image = _repair_schnell_output_with_qwen(
                            source, target, indexed_prompt, width_value, height_value, name,
                            job_id=job_id, asset_kind=asset_kind,
                        )
                    image.update({"url":f"/api/result-media?filename={target.name}&subfolder=images", "filename":target.name,
                                  "subfolder":"images", "reference_url":reference_url, "repair_requested":True})
                elif parsed.path in {"/api/characters/generate", "/api/shots/generate", "/api/shots/repair"} and references and asset_kind not in {"scene", "prop"}:
                    reference_url = str(references[0].get("url", ""))
                    clothing_reference_url = str(body.get("clothing_reference_url") or references[0].get("clothing_url") or reference_url)
                    target_pose = str(body.get("target_pose") or "")
                    validation_evidence = ""
                    variant_attempts = 2 if asset_phase == "variant" and target_pose else 1
                    for variant_attempt in range(variant_attempts):
                        pose_retry = {
                            "left_45_full":"上一张过度旋转成了侧面。本次从正面只向人物左侧转约35度；必须同时看见双眼、远侧脸颊和躯干正面，严禁90度侧脸。",
                            "right_45_full":"上一张过度旋转成了侧面。本次从正面只向人物右侧转约35度；必须同时看见双眼、远侧脸颊和躯干正面，严禁90度侧脸。",
                            "side_90_full":"本次必须是严格90度纯侧面，只看见一侧面部轮廓。",
                            "back_full":"本次必须严格背对镜头，面部完全不可见。",
                        }.get(target_pose, "本次必须严格纠正目标方向。")
                        retry_prompt = indexed_prompt if variant_attempt == 0 else (
                            f"{indexed_prompt}\n上一张候选未通过机器预审。{pose_retry}同时保持人物身份、发型服装、自然头身比和脚底完整入画。"
                        )
                        with _claim_production_resource("image", job_id, timeout=IMAGE_QUEUE_TIMEOUT_SECONDS):
                            if asset_phase == "variant" and target_pose:
                                image = _invoke_production_capability(
                                    "image.variant.qwen", name=name, prompt=retry_prompt, width=body.get("width"), height=body.get("height"),
                                    identity_reference_url=reference_url, clothing_reference_url=clothing_reference_url, target_pose=target_pose,
                                    character_sheet_urls=[str(item.get("url") or "") for item in references[1:] if item.get("url")], job_id=job_id,
                                )
                            else:
                                image = _invoke_production_capability(
                                    "image.variant.ipadapter", name=name, prompt=retry_prompt, width=body.get("width"), height=body.get("height"),
                                    reference_url=reference_url, pose_reference_url=str(body.get("pose_reference_url") or references[0].get("pose_url") or ""),
                                    target_pose=target_pose, clothing_reference_url=clothing_reference_url,
                                    character_gender=str(body.get("character_gender") or ""), job_id=job_id,
                                )
                        if asset_phase != "variant" or not target_pose:
                            break
                        if target_pose != "front_half":
                            normalized, frame_evidence = _prepare_character_full_frame_candidate(image)
                            if not normalized:
                                validation_evidence = json.dumps({"exactly_one_person":False, **frame_evidence}, ensure_ascii=False)
                                if variant_attempt == variant_attempts - 1:
                                    raise RuntimeError(f"人物固定角度视觉验收失败：{validation_evidence}")
                                continue
                        validation_deadline = time.monotonic() + IMAGE_VALIDATION_TIMEOUT_SECONDS
                        valid, validation_evidence = _run_image_validation(
                            job_id,
                            "character_validation",
                            lambda candidate: _validate_character_variant(
                                reference_url,
                                candidate,
                                target_pose,
                                clothing_reference_url,
                                job_id=job_id,
                                deadline=validation_deadline,
                            ),
                            image,
                        )
                        image["validation_evidence"] = validation_evidence
                        image["validation_passed"] = valid
                        if valid:
                            break
                        _local_media_path(image.get("url")).unlink(missing_ok=True)
                        if variant_attempt == variant_attempts - 1:
                            raise RuntimeError(f"人物固定角度视觉验收失败：{validation_evidence}")
                else:
                    if references and asset_phase == "variant" and asset_kind in {"scene", "prop"}:
                        reference_url = str(references[0].get("url", ""))
                        variant_prompt = (
                            f"生成{asset_kind}固定角度资产图，观察角度严格为{str(body.get('target_pose') or '指定角度')}；"
                            f"主体名称、结构、材质、颜色、比例、环境风格和光影必须严格遵循资产描述。{indexed_prompt}"
                        )
                        image = _invoke_production_capability(
                            "image.generate", name=name, prompt=variant_prompt, width=body.get("width"), height=body.get("height"),
                            lora=None, job_id=job_id, guidance=1.5, steps=20,
                            model=ASSET_3D_KLEIN9B_MODEL, base_model="flux2-klein-9b", quantize=8,
                        )
                        image.update({"reference_url":reference_url, "target_pose":str(body.get("target_pose") or ""),
                                      "generation_workflow":"FLUX.2 Klein 9B MLX 8-bit", "workflow_mode":"direct_fixed_angle_no_qwen",
                                      "base_model":"flux2-klein-9b", "quantization":"8-bit", "cfg":1.5, "steps":20})
                    else:
                        image = (_invoke_production_capability("image.baseline.klein9b", name=name, prompt=indexed_prompt, width=body.get("width"), height=body.get("height"), job_id=job_id, body=body)
                                 if parsed.path == "/api/characters/generate" and asset_phase == "baseline"
                                 else _invoke_production_capability("image.generate", name=name, prompt=indexed_prompt, width=body.get("width"), height=body.get("height"), lora=selected_lora, job_id=job_id))
                    if parsed.path == "/api/characters/generate" and asset_kind == "character" and asset_phase == "baseline":
                        validation_evidence = ""
                        baseline_required_checks = (
                            "correct_orientation", "required_928x1664", "deterministic_full_frame",
                            *CHARACTER_FULL_BODY_ANATOMY_CHECKS,
                        )
                        def validate_baseline_candidate(candidate: dict) -> tuple[bool, str]:
                            candidate["orientation_mirrored"] = False
                            validation_deadline = time.monotonic() + IMAGE_VALIDATION_TIMEOUT_SECONDS
                            _, candidate_evidence = _run_image_validation(
                                job_id,
                                "character_validation",
                                lambda current: _validate_character_variant(
                                    current.get("url", ""),
                                    current,
                                    "front_full",
                                    job_id=job_id,
                                    deadline=validation_deadline,
                                ),
                                candidate,
                            )
                            try:
                                verdict = json.loads(candidate_evidence)
                                candidate_valid = all(verdict.get(key) is True for key in baseline_required_checks)
                            except (json.JSONDecodeError, TypeError):
                                candidate_valid = False
                            return candidate_valid, candidate_evidence

                        def generate_baseline_retry(retry_number: int, previous_evidence: str) -> dict:
                            try:
                                verdict = json.loads(previous_evidence)
                                failed_checks = [key for key in baseline_required_checks if verdict.get(key) is not True]
                            except (json.JSONDecodeError, TypeError):
                                failed_checks = []
                            correction = "、".join(failed_checks) or "foreground_segmentation_or_front_full_body_composition"
                            retry_prompt = (
                                f"{indexed_prompt}\nThe previous candidate failed one or more strict checks. "
                                f"Failed required checks: {correction}. This is automatic retry {retry_number - 1} of 2. "
                                "Regenerate one strict zero-degree front-facing full-body identity reference. Face, shoulders, torso, pelvis, knees and feet must be square to camera; yaw and roll must be near zero. Show complete hair to both shoes in a neutral standing A-pose on a gray studio background, with at least 8 percent clear background above the hair and at least 3 percent clear background below the shoe soles; these are minimum margins, not fixed targets. "
                                "Match every stated age, gender, face, hair, garment type and garment color attribute; never crop limbs or substitute clothing. Every visible arm, wrist, hand, finger, leg, ankle, foot and toe must be anatomically complete and separate, with no fused, missing, extra, duplicated, broken, melted or disconnected limb or digit."
                            )
                            return _invoke_production_capability(
                                "image.baseline.klein9b", name=f"{name}_front_retry_{retry_number}", prompt=retry_prompt,
                                width=body.get("width"), height=body.get("height"), job_id=job_id, body=body,
                            )

                        try:
                            image, validation_evidence, validation_attempts = _run_character_full_frame_candidate_loop(
                                image, generate_retry=generate_baseline_retry,
                                validate_candidate=validate_baseline_candidate, max_attempts=3,
                                on_attempt=lambda attempt: _update_image_job(
                                    job_id, validation_attempts=attempt, heartbeat_at=_iso_now(),
                                ),
                            )
                        except RuntimeError as error:
                            detail = str(error).split(":", 1)[-1]
                            try:
                                failed_verdict = json.loads(detail)
                                failed_checks = [key for key in baseline_required_checks if failed_verdict.get(key) is not True]
                                detail = "、".join({
                                    "correct_orientation":"0度正面方向",
                                    "required_928x1664":"928×1664尺寸",
                                    "deterministic_full_frame":"头顶/脚底安全区",
                                }.get(key, key) for key in failed_checks) or "轮廓识别或安全区"
                            except (json.JSONDecodeError, TypeError):
                                detail = "轮廓识别或安全区"
                            raise RuntimeError(f"人物0度正面全身基准图自动生成3次仍未通过规范验收：{detail}") from error
                        image["validation_evidence"] = validation_evidence
                        image["validation_passed"] = True
                        image["validation_attempts"] = validation_attempts
                    if parsed.path == "/api/characters/generate" and asset_kind == "prop":
                        validation_evidence = ""
                        for validation_attempt in range(2):
                            prop_valid, validation_evidence = _run_image_validation(
                                job_id, "prop_validation",
                                lambda candidate: _validate_prop_asset(candidate, job_id=job_id), image,
                            )
                            image["validation_evidence"] = validation_evidence
                            image["validation_passed"] = prop_valid
                            if prop_valid: break
                            invalid = _local_media_path(image.get("url")); invalid.unlink(missing_ok=True)
                            if validation_attempt == 1: raise RuntimeError(f"道具资产验收失败：{validation_evidence}")
                            retry_prompt = f"{indexed_prompt}\n重新生成：上一张不是合格单道具产品图。本次只允许单个道具本体、无缝纯中性灰背景；禁止任何场景、建筑、商店、街道、家具、文字、招牌、人物和人体。"
                            image = (_invoke_production_capability("image.generate", name=f"{name}_no_person_retry", prompt=retry_prompt, width=body.get("width"), height=body.get("height"), lora=None, job_id=job_id, guidance=1.5, steps=20, model=ASSET_3D_KLEIN9B_MODEL, base_model="flux2-klein-9b", quantize=8)
                                     if references and asset_phase == "variant"
                                     else _invoke_production_capability("image.baseline.klein9b", name=f"{name}_no_person_retry", prompt=retry_prompt, width=body.get("width"), height=body.get("height"), job_id=job_id, body=body)
                                     if asset_phase == "baseline"
                                     else _invoke_production_capability("image.generate", name=f"{name}_no_person_retry", prompt=retry_prompt, width=body.get("width"), height=body.get("height"), lora=selected_lora, job_id=job_id))
                    if parsed.path == "/api/characters/generate" and asset_kind == "scene":
                        validation_evidence = ""
                        for validation_attempt in range(3):
                            scene_valid, validation_evidence = _run_image_validation(
                                job_id, "scene_validation",
                                lambda candidate: _validate_scene_asset(candidate, job_id=job_id), image,
                            )
                            image["validation_evidence"] = validation_evidence
                            image["validation_passed"] = scene_valid
                            if scene_valid:
                                break
                            _local_media_path(image.get("url")).unlink(missing_ok=True)
                            if validation_attempt == 2:
                                raise RuntimeError(f"场景资产验收失败：{validation_evidence}")
                            retry_prompt = (
                                f"{indexed_prompt}\nEMPTY ARCHITECTURAL ENVIRONMENT ONLY. "
                                "No person, human figure, silhouette, statue, poster, title, Chinese character, letter, number, sign, logo, caption or watermark. "
                                "Do not render the camera-angle description as typography."
                            )
                            image = (_invoke_production_capability("image.generate", name=f"{name}_empty_scene_retry_{validation_attempt + 2}", prompt=retry_prompt, width=body.get("width"), height=body.get("height"), lora=None, job_id=job_id, guidance=1.5, steps=20, model=ASSET_3D_KLEIN9B_MODEL, base_model="flux2-klein-9b", quantize=8)
                                     if references and asset_phase == "variant"
                                     else _invoke_production_capability("image.baseline.klein9b", name=f"{name}_empty_scene_retry_{validation_attempt + 2}", prompt=retry_prompt, width=body.get("width"), height=body.get("height"), job_id=job_id, body=body)
                                     if asset_phase == "baseline"
                                     else _invoke_production_capability("image.generate", name=f"{name}_empty_scene_retry_{validation_attempt + 2}", prompt=retry_prompt, width=body.get("width"), height=body.get("height"), lora=None, job_id=job_id))
                if references and asset_phase == "variant" and asset_kind in {"scene", "prop"}:
                    image.update({
                        "reference_url":str(references[0].get("url", "")),
                        "target_pose":str(body.get("target_pose") or ""),
                        "generation_workflow":"FLUX.2 Klein 9B MLX 8-bit",
                        "workflow_mode":"direct_fixed_angle_no_qwen",
                        "base_model":"flux2-klein-9b",
                        "quantization":"8-bit",
                        "cfg":1.5,
                        "steps":20,
                    })
                if required_text:
                    text_metadata = _apply_required_text_overlay(_local_media_path(image.get("url")), required_text, body)
                    image.update(text_metadata)
                with IMAGE_JOB_LOCK:
                    jobs = _load_image_jobs(); job = jobs.setdefault("jobs", {}).setdefault(job_id, {})
                    if job.get("status") == "failed":
                        raise RuntimeError(str(job.get("error") or "图片任务已停止"))
                    job.update({"image":image, "status":"completed", "heartbeat_at":_iso_now(), "finished_at":_iso_now(),
                                "pid":None, "process_group":None, "error":""})
                    if is_character_generation and asset_kind == "character" and asset_phase == "baseline":
                        job["validation_attempts"] = int(image.get("validation_attempts") or 0)
                    payload = dict(job) if is_character_generation else {"image":image, "job_id":job_id}
                    _save_image_jobs(jobs)
                return self._json(HTTPStatus.OK, payload)
            except Exception as error:
                message = f"图片生成失败：{error}"
                terminal_updates = {"status":"failed", "error":message, "finished_at":_iso_now(),
                                    "heartbeat_at":_iso_now(), "pid":None, "process_group":None}
                terminal = _update_image_job(job_id, **terminal_updates)
                error_payload = {"error": message}
                if is_character_generation and requested_kind == "character" and requested_phase == "baseline":
                    error_payload["validation_attempts"] = int(terminal.get("validation_attempts") or 0)
                return self._json(HTTPStatus.BAD_GATEWAY, error_payload)
            finally:
                with IMAGE_JOB_LOCK:
                    ACTIVE_IMAGE_JOBS.discard(job_id)
                    ACTIVE_IMAGE_WORKERS.pop(job_id, None)
                    if ACTIVE_IMAGE_SUBJECTS.get(subject_key) == job_id: ACTIVE_IMAGE_SUBJECTS.pop(subject_key, None)
        if parsed.path == "/api/videos/generate":
            subject_key = _video_key(body)
            ready, memory = _memory_ready(VIDEO_ESTIMATED_MEMORY)
            with VIDEO_JOB_LOCK:
                jobs = _load_video_jobs(); matches = [job for job in jobs.setdefault("jobs", {}).values() if job.get("subject_key") == subject_key and job.get("status") in {"waiting_memory", "generating"}]
                if matches: return self._json(HTTPStatus.CONFLICT, {**matches[-1], "error":"video_subject_active"})
                job_id = str(uuid4())
                status = "generating" if ready and not ACTIVE_VIDEO_JOBS and not _heavy_task_busy() else "waiting_memory"
                jobs["jobs"][job_id] = {"job_id":job_id, "subject_key":subject_key, "status":status, "stage":"queued" if status == "waiting_memory" else "starting", "request":body, "memory":memory, "queued_at":_iso_now(), "heartbeat_at":_iso_now(), "timeout_seconds":VIDEO_TASK_TIMEOUT_SECONDS, "pid":None, "process_group":None}; _save_video_jobs(jobs)
                if status == "generating": ACTIVE_VIDEO_JOBS.add(job_id); ACTIVE_VIDEO_SUBJECTS[subject_key] = job_id
            if status == "generating":
                threading.Thread(target=_invoke_production_capability, args=("video.shot",), kwargs={"job_id":job_id, "body":body}, daemon=True, name=f"video-{job_id[:8]}").start()
            return self._json(HTTPStatus.ACCEPTED, {"job_id":job_id, "status":status, "memory":memory})
        if parsed.path == "/api/audio/tts":
            try:
                return self._json(HTTPStatus.OK, _invoke_production_capability("audio.tts", body=body))
            except ValueError as error:
                return self._json(HTTPStatus.BAD_REQUEST, {"error":str(error)})
            except Exception as error:
                return self._json(HTTPStatus.BAD_GATEWAY, {"error": f"本地配音生成失败：{str(error)[:500]}"})
        if parsed.path in {"/api/videos/lipsync", "/api/videos/latentsync"}:
            try:
                capability = "video.lipsync" if parsed.path.endswith("lipsync") else "video.lipsync.fallback"
                return self._json(HTTPStatus.OK, _invoke_production_capability(capability, body=body))
            except Exception as error:
                return self._json(HTTPStatus.BAD_GATEWAY, {"error": f"口型同步失败：{str(error)[:500]}"})
        if parsed.path in {"/api/audio/speaker-audit", "/api/audio/emotion-audit"}:
            capability = "audit.audio.speaker" if parsed.path.endswith("speaker-audit") else "audit.audio.emotion"
            status, result = _optional_audit(capability, body)
            return self._json(status, result)
        if parsed.path == "/api/videos/lipsync-audit":
            status, result = _optional_audit("audit.video.lipsync", body)
            return self._json(status, result)
        if parsed.path == "/api/videos/audio-repair":
            try:
                return self._json(HTTPStatus.OK, _invoke_production_capability("audio.repair", body=body))
            except Exception as error: return self._json(HTTPStatus.BAD_GATEWAY, {"error": f"音频混合失败：{str(error)[:500]}"})
        if parsed.path in {"/api/videos/face-consistency-audit", "/api/videos/continuity-audit"}:
            capability = "audit.video.face_consistency" if parsed.path.endswith("face-consistency-audit") else "audit.video.continuity"
            status, result = _optional_audit(capability, body)
            return self._json(status, result)
        if parsed.path == "/api/videos/merge":
            try:
                return self._json(HTTPStatus.OK, _invoke_production_capability("composition.merge", body=body))
            except Exception as error: return self._json(HTTPStatus.BAD_GATEWAY, {"error":f"合并成片失败：{str(error)[:500]}"})
        if parsed.path == "/api/videos/subtitles/reburn":
            try:
                return self._json(HTTPStatus.OK, _invoke_production_capability("subtitle.reburn", body=body))
            except Exception as error: return self._json(HTTPStatus.BAD_GATEWAY, {"error":f"字幕烧录失败：{str(error)[:500]}"})
        if parsed.path in {"/api/subtitles/text-audit", "/api/subtitles/ocr-audit", "/api/subtitles/speech-audit"}:
            if not parsed.path.endswith("text-audit"):
                capability = "audit.subtitle.ocr" if parsed.path.endswith("ocr-audit") else "audit.subtitle.speech_alignment"
                status, result = _optional_audit(capability, body)
                return self._json(status, result)
            return self._json(HTTPStatus.OK, _invoke_production_capability("audit.subtitle.text", body=body))
        if parsed.path == "/api/videos/audit":
            return self._json(HTTPStatus.OK, _invoke_production_capability("audit.video.final", body=body))
        if parsed.path == "/api/repair/plan":
            return self._json(HTTPStatus.OK, {"plan":[{"target":"manual_review", "shot_id":item.get("shot_id"), "disposition":"manual_review"} for item in body.get("errors", [])]})
        if parsed.path == "/api/videos/upscale/quote":
            duration = sum(_media_duration(_resolve_media_input(path)) for path in body.get("paths", []))
            return self._json(HTTPStatus.OK, {"duration_seconds":duration, "points":max(1, int(duration + 0.999)), "estimated_seconds":max(1, int(duration * 2))})
        if parsed.path == "/api/videos/upscale":
            try:
                return self._json(HTTPStatus.OK, _invoke_production_capability("video.upscale", body=body))
            except Exception as error: return self._json(HTTPStatus.BAD_GATEWAY, {"error":f"超分降噪失败：{str(error)[:500]}"})
        if parsed.path == "/api/images/upscale":
            try:
                return self._json(HTTPStatus.OK, _invoke_production_capability("image.upscale", body=body))
            except Exception as error: return self._json(HTTPStatus.BAD_GATEWAY, {"error":f"图片超分失败：{str(error)[:500]}"})
        if parsed.path == "/api/images/identity-refine":
            try:
                return self._json(HTTPStatus.OK, _invoke_production_capability("image.identity_refine", body=body))
            except Exception as error: return self._json(HTTPStatus.BAD_GATEWAY, {"error":f"人物身份修正失败：{str(error)[:500]}"})
        if parsed.path == "/api/videos/import-audit":
            try:
                return self._json(HTTPStatus.OK, _invoke_production_capability("audit.media.import", body=body))
            except Exception as error: return self._json(HTTPStatus.BAD_REQUEST, {"error":f"导入媒体审核失败：{str(error)[:500]}"})
        if parsed.path == "/api/exports/create":
            try:
                return self._json(HTTPStatus.OK, _invoke_production_capability("export.package", body=body))
            except Exception as error: return self._json(HTTPStatus.BAD_GATEWAY, {"error":f"成果导出失败：{str(error)[:500]}"})
        if parsed.path in {"/api/characters/stop", "/api/images/stop"}:
            stop_stage = str(body.get("stage") or ("assets" if parsed.path == "/api/characters/stop" else "image"))
            stage_cancelled = _cancel_scoped_production_stage(body, stop_stage)
            targets = _stop_image_generation(project_id=str(body.get("project_id") or ""), requested_name=str(body.get("name") or ""), stop_all=bool(body.get("all")), identity=body)
            return self._json(HTTPStatus.OK, {"ok":True, "stopped":targets, "stage_cancelled":stage_cancelled})
        if parsed.path == "/api/videos/stop":
            stage_cancelled = _cancel_scoped_production_stage(body, "video")
            subjects = []
            for key in body.get("keys") or []:
                parts = str(key).split(":", 1)
                if len(parts) == 2 and all(str(body.get(name) or "").strip() for name in ("tenant_id", "user_id", "project_id")):
                    subjects.append(":".join((str(body["tenant_id"]), str(body["user_id"]), str(body["project_id"]), parts[0], parts[1])))
            if not subjects and all(body.get(key) is not None for key in ("tenant_id", "user_id", "project_id", "episode", "shot_number")):
                subjects.append(_video_key(body))
            targets = []
            if body.get("job_id"):
                targets.extend(_stop_video_generation(requested_job_id=str(body.get("job_id") or ""), identity=body))
            for subject_key in dict.fromkeys(subjects):
                targets.extend(_stop_video_generation(subject_key=subject_key, identity=body))
            return self._json(HTTPStatus.OK, {"ok":True, "stopped":targets, "stage_cancelled":stage_cancelled})
        if parsed.path == "/api/tasks/stop":
            operation_key = str(body.get("operation_key") or ""); project_id = str(body.get("project_id") or "")
            parts = operation_key.split(":")
            if len(parts) < 3 or parts[0] != "project" or parts[1] != project_id:
                return self._json(HTTPStatus.BAD_REQUEST, {"error":"invalid_operation_key"})
            stage = parts[2]
            if stage in {"outline", "script"}:
                stage_cancelled = _cancel_scoped_production_stage(body, stage)
                ok, stopped, error = _stop_text_generation(stage=stage, project_id=project_id, identity=body)
                return self._json(HTTPStatus.OK if ok else HTTPStatus.SERVICE_UNAVAILABLE, {"stopped":bool(stopped or stage_cancelled), "status":"cancelled" if stopped or stage_cancelled else "idle", "job_ids":stopped, "stage_cancelled":stage_cancelled, **({"error":error} if error else {})})
            if stage == "shot_videos" and len(parts) >= 5:
                stage_cancelled = _cancel_scoped_production_stage(body, "video")
                subject = f"{body.get('tenant_id', '')}:{body.get('user_id', '')}:{project_id}:{parts[3]}:{parts[4]}"
                stopped = _stop_video_generation(subject_key=subject, identity=body)
                return self._json(HTTPStatus.OK, {"stopped":bool(stopped or stage_cancelled), "status":"cancelled" if stopped or stage_cancelled else "idle", "job_ids":stopped, "stage_cancelled":stage_cancelled})
            if stage in {"shot_images", "assets"}:
                canonical = "image" if stage == "shot_images" else "assets"
                stage_cancelled = _cancel_scoped_production_stage(body, canonical)
                stopped = _stop_image_generation(project_id=project_id, stop_all=True, identity=body)
                return self._json(HTTPStatus.OK, {"stopped":bool(stopped or stage_cancelled), "status":"cancelled" if stopped or stage_cancelled else "idle", "job_ids":stopped, "stage_cancelled":stage_cancelled})
            if stage == "storyboard":
                stage_cancelled = _cancel_scoped_production_stage(body, "storyboard")
                return self._json(HTTPStatus.OK, {"stopped":bool(stage_cancelled), "status":"cancelled" if stage_cancelled else "idle", "job_ids":[], "stage_cancelled":stage_cancelled})
            if stage in {"composition", "merged_episodes", "review_export", "final_audit", "export", "upscale"}:
                canonical = "composition" if stage in {"composition", "merged_episodes"} else "review_export"
                stage_cancelled = _cancel_scoped_production_stage(body, canonical)
                return self._json(HTTPStatus.OK, {"stopped":bool(stage_cancelled), "status":"cancelled" if stage_cancelled else "idle", "job_ids":[], "stage_cancelled":stage_cancelled})
            return self._json(HTTPStatus.CONFLICT, {"error":"task_not_stoppable", "message":"该阶段没有正在运行的可停止进程"})
        if parsed.path == "/api/tasks/resume":
            operation_key = str(body.get("operation_key") or "")
            resumed, evidence = _resume_persisted_task(body, operation_key)
            if not resumed:
                return self._json(HTTPStatus.CONFLICT, {"error":evidence, "message":"没有可安全重放的持久请求"})
            return self._json(HTTPStatus.ACCEPTED, {"resumed":True, "operation_key":operation_key, "endpoint":evidence})
        if parsed.path == "/api/shots/semantic-audit":
            try:
                return self._json(HTTPStatus.OK, _audit_shot_consistency(body))
            except Exception as error:
                return self._json(HTTPStatus.BAD_GATEWAY, {"error":f"分镜一致性审核失败：{str(error)[:300]}"})
        if parsed.path.startswith("/api/production/"):
            try:
                if parsed.path == "/api/production/scopes":
                    return self._json(HTTPStatus.OK, {"record": PRODUCTION_LEDGER.upsert_projection(body)})
                if parsed.path == "/api/production/scopes/bulk":
                    records = body.get("records") if isinstance(body.get("records"), list) else []
                    saved = PRODUCTION_LEDGER.upsert_many_projection(records, replace=bool(body.get("replace_batch_scope_sets")))
                    identity = next(({key:str(record.get(key) or "") for key in ("tenant_id", "user_id", "project_id")} for record in records), {})
                    if all(identity.get(key) for key in ("tenant_id", "user_id", "project_id")):
                        _reconcile_completed_production_stages(identity, PRODUCTION_LEDGER.list(identity))
                    return self._json(HTTPStatus.OK, {"records":saved})
                if parsed.path == "/api/production/scopes/confirm":
                    record, workflow = _confirm_production_scope(body)
                    return self._json(HTTPStatus.OK, {"record": record, "workflow":workflow})
                if parsed.path == "/api/production/assets/confirm":
                    payload = {**body, "stage": "assets", "scope_type": "asset", "lifecycle": "pending_confirmation"}
                    try: PRODUCTION_LEDGER.upsert(payload)
                    except ProductionLedgerError: pass
                    record, workflow = _confirm_asset_scope_deferred(payload)
                    return self._json(HTTPStatus.OK, {"record":record, "workflow":workflow})
                if parsed.path == "/api/production/episode-batches/confirm":
                    records = []
                    rejected = {str(value) for value in body.get("rejected_scope_ids", [])}
                    for scope_id in body.get("scope_ids", []):
                        if canonical_stage(body.get("stage")) == "review_export" and str(scope_id).startswith("upscale:"):
                            raise ProductionLedgerError("upscale scopes require exact-generation confirmation")
                        payload = {**body, "scope_type": "episode", "scope_id": str(scope_id), "lifecycle": "failed" if str(scope_id) in rejected else "pending_confirmation", "error": body.get("rejection_reason", "") if str(scope_id) in rejected else ""}
                        record = PRODUCTION_LEDGER.upsert(payload)
                        records.append(record if str(scope_id) in rejected else _confirm_production_scope(payload)[0])
                    return self._json(HTTPStatus.OK, {"records": records})
                if parsed.path == "/api/production/dependencies":
                    PRODUCTION_LEDGER.dependency(body)
                    return self._json(HTTPStatus.OK, {"ok": True})
                if parsed.path == "/api/production/dependencies/bulk":
                    PRODUCTION_LEDGER.dependencies(body.get("dependencies") if isinstance(body.get("dependencies"), list) else [])
                    return self._json(HTTPStatus.OK, {"ok": True})
                if parsed.path == "/api/production/impact-preview":
                    return self._json(HTTPStatus.OK, {"records": PRODUCTION_LEDGER.impact(body, mutate=False)})
                if parsed.path == "/api/production/invalidate":
                    return self._json(HTTPStatus.OK, {"records": PRODUCTION_LEDGER.impact(body, mutate=True)})
                if parsed.path == "/api/production/confirmations/withdraw":
                    return self._json(HTTPStatus.OK, {"records": PRODUCTION_LEDGER.withdraw(body)})
                if parsed.path == "/api/production/workflow/report":
                    lifecycle = str(body.get("lifecycle", ""))
                    if lifecycle == "completed":
                        return self._json(HTTPStatus.CONFLICT, {"error":"confirmation_required", "message":"阶段完成只能通过持久确认接口写入"})
                    workflow = _production_orchestrator().report(body, str(body.get("stage", "")), lifecycle, evidence=body.get("evidence"))
                    return self._json(HTTPStatus.OK, {"workflow":workflow})
                return self._json(HTTPStatus.NOT_FOUND, {"error": "production_operation_not_found"})
            except ProductionLedgerError as error:
                return self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid_production_operation", "message": str(error)})
            except ValueError as error:
                return self._json(HTTPStatus.CONFLICT, {"error":"production_stage_conflict", "message":str(error)})
        if parsed.path == "/api/projects/version":
            with PROJECT_STORE_LOCK:
                store = _load_store()
                project = self._find(store, body.get("project_id", ""), body.get("tenant_id", ""), body.get("user_id", ""))
                if not project: return self._json(HTTPStatus.NOT_FOUND, {"error":"project_not_found"})
                version = _create_project_version(project, body.get("stage"), body.get("reason"))
            return self._json(HTTPStatus.OK, {"version":version, **version})
        if parsed.path == "/api/projects/version/rollback":
            with PROJECT_STORE_LOCK:
                record = _read_project_version(body.get("version_id"))
                if not record or str(record.get("project_id", "")) != str(body.get("project_id", "")):
                    return self._json(HTTPStatus.NOT_FOUND, {"error":"version_not_found"})
                store = _load_store(); current = self._find(store, body.get("project_id", ""), body.get("tenant_id", ""), body.get("user_id", ""))
                if not current: return self._json(HTTPStatus.NOT_FOUND, {"error":"project_not_found"})
                restored = record.get("project")
                if not isinstance(restored, dict): return self._json(HTTPStatus.CONFLICT, {"error":"invalid_version"})
                _create_project_version(current, "before-rollback", f"回滚到 {body.get('version_id')}")
                index = store["projects"].index(current); store["projects"][index] = restored; _save_store(store)
            return self._json(HTTPStatus.OK, {"ok":True, "project":restored, "version_id":body.get("version_id")})
        if parsed.path in {"/api/projects/archive", "/api/projects/restore", "/api/projects/delete"}:
            with PROJECT_STORE_LOCK:
                store = _load_store(); project = self._find(store, body.get("id", ""), body.get("tenant_id", ""), body.get("user_id", ""))
                if not project: return self._json(HTTPStatus.NOT_FOUND, {"error": "project_not_found"})
                version = _create_project_version(project, "before-delete" if parsed.path.endswith("delete") else "before-archive-change", parsed.path)
                if parsed.path == "/api/projects/delete": store["projects"].remove(project)
                else:
                    project["archived"] = parsed.path.endswith("archive")
                    project["archived_at"] = datetime.now(UTC).isoformat() if project["archived"] else None
                _save_store(store); return self._json(HTTPStatus.OK, {"ok": True, "project": project, "version":version})
        if parsed.path == "/api/resources":
            data_url = str(body.get("data_url", "")); match = re.match(r"data:([^;]+);base64,(.+)", data_url, re.DOTALL)
            if not match: return self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid_resource_data"})
            suffix = mimetypes.guess_extension(match.group(1)) or ".bin"; resource_id = str(uuid4())
            target = OUTPUT_ROOT / "resources" / f"{resource_id}{suffix}"; target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(base64.b64decode(match.group(2)))
            resource = {key: body.get(key) for key in ("tenant_id", "user_id", "project_id", "plugin_key", "scope", "kind", "name", "metadata")}
            stamp = datetime.now(UTC).isoformat()
            resource.update({"id": resource_id, "filename": target.name, "subfolder": "resources", "url": f"/api/result-media?filename={target.name}&subfolder=resources", "created_at": stamp, "updated_at": stamp})
            store = _load_resources(); store.setdefault("resources", []).append(resource); _save_resources(store)
            return self._json(HTTPStatus.OK, {"resource": resource})
        if parsed.path == "/api/resources/delete":
            store = _load_resources(); resource_id = str(body.get("id", "")); store["resources"] = [item for item in store.get("resources", []) if item.get("id") != resource_id]; _save_resources(store)
            return self._json(HTTPStatus.OK, {"ok": True})
        if parsed.path == "/api/projects/stage":
            try:
                stage = _write_project_stage(
                    str(body.get("id", "")), str(body.get("tenant_id", "")), str(body.get("user_id", "")),
                    str(body.get("stage", "")), body.get("data", {}) if isinstance(body.get("data", {}), dict) else {},
                    projection_only=True,
                )
            except LookupError:
                return self._json(HTTPStatus.NOT_FOUND, {"error":"project_not_found"})
            except StoryBibleError as error:
                return self._json(HTTPStatus.CONFLICT, {"error":"story_bible_conflict", "message":str(error)})
            except ValueError:
                return self._json(HTTPStatus.CONFLICT, {"error":"stale_asset_census"})
            return self._json(HTTPStatus.OK, {"stage": stage})
        if parsed.path == "/api/projects/stage/watch/cancel":
            try:
                watch_key = _project_stage_watch_key(
                    str(body.get("tenant_id") or ""), str(body.get("user_id") or ""), str(body.get("id") or ""),
                    str(body.get("stage") or ""), str(body.get("request_id") or ""),
                )
            except ValueError: return self._json(HTTPStatus.BAD_REQUEST, {"error":"invalid_watch_scope"})
            with PROJECT_STAGE_CONDITION:
                _reap_cancelled_stage_watches()
                PROJECT_STAGE_CANCELLED_WATCHES[watch_key] = time.monotonic()
                PROJECT_STAGE_CONDITION.notify_all()
            return self._json(HTTPStatus.OK, {"cancelled":True, "request_id":watch_key[-1]})
        if parsed.path in {"/api/projects/create", "/api/projects/update", "/api/projects/pin"}:
            with PROJECT_STORE_LOCK:
                store = _load_store()
                stamp = datetime.now(UTC).isoformat()
                project = self._find(store, body.get("id", ""), body.get("tenant_id", ""), body.get("user_id", "")) if body.get("id") else None
                if parsed.path in {"/api/projects/create", "/api/projects/update"}:
                    try:
                        _validate_project_visual_style(body)
                    except ValueError:
                        return self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid_visual_style"})
                if parsed.path == "/api/projects/create":
                    project = {**body, "id": body.get("id") or str(uuid4()), "pinned": False, "archived": False, "archived_at": None, "collaborators": [], "stage_state": {}, "created_at": stamp, "updated_at": stamp}
                    store.setdefault("projects", []).append(project)
                elif not project:
                    return self._json(HTTPStatus.NOT_FOUND, {"error": "project_not_found"})
                elif parsed.path == "/api/projects/update":
                    preserved = {key: project.get(key) for key in ("pinned", "archived", "archived_at", "collaborators", "stage_state", "created_at")}
                    project.clear(); project.update(body); project.update(preserved); project["updated_at"] = stamp
                else:
                    project["pinned"] = not bool(project.get("pinned")); project["updated_at"] = stamp
                _save_store(store)
            return self._json(HTTPStatus.OK, {"project": project})
        return self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    @staticmethod
    def _find(store: dict, project_id: str, tenant: str, user: str) -> dict | None:
        return next((item for item in store.get("projects", []) if item.get("id") == project_id and item.get("tenant_id") == tenant and item.get("user_id") == user), None)

    def _project(self, project_id: str, tenant: str, user: str) -> dict | None:
        with PROJECT_STORE_LOCK:
            return self._find(_load_store(), project_id, tenant, user)

    def _body(self) -> dict | None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            return json.loads(self.rfile.read(length)) if 0 < length <= 40_000_000 else None
        except (ValueError, json.JSONDecodeError):
            return None

    def _media(self, parsed) -> None:
        query = parse_qs(parsed.query)
        filename = unquote(query.get("filename", [""])[0]).lstrip("/")
        subfolder = unquote(query.get("subfolder", [""])[0]).strip("/")
        relative = Path(subfolder) / filename if subfolder and "/" not in filename else Path(filename)
        target = (OUTPUT_ROOT / relative).resolve()
        if OUTPUT_ROOT not in target.parents or not target.is_file():
            return self._json(HTTPStatus.NOT_FOUND, {"error": "media_not_found"})
        content = target.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mimetypes.guess_type(target.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.end_headers(); self.wfile.write(content)

    def _json(self, status: HTTPStatus, payload: dict) -> None:
        content = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status); self.send_header("Content-Type", "application/json; charset=utf-8"); self.send_header("Content-Length", str(len(content))); self.end_headers(); self.wfile.write(content)

    def log_message(self, format: str, *args) -> None:
        return


def main() -> None:
    _recover_asset_3d_archive_backups()
    _recover_agent_jobs()
    _recover_image_jobs()
    _recover_text_jobs()
    _recover_video_jobs()
    _replay_durable_task_projections()
    _recover_production_workflows()
    monitor = threading.Thread(target=_monitor_waiting_video_jobs, daemon=True, name="video-memory-monitor")
    monitor.start()
    image_monitor = threading.Thread(target=_monitor_image_jobs, daemon=True, name="image-task-watchdog")
    image_monitor.start()
    text_monitor = threading.Thread(target=_monitor_text_jobs, daemon=True, name="text-task-watchdog")
    text_monitor.start()
    worker_monitor = threading.Thread(target=_monitor_local_worker, daemon=True, name="production-worker-heartbeat")
    worker_monitor.start()
    stage_watch_monitor = threading.Thread(target=_monitor_project_stage_watches, daemon=True, name="project-stage-watch-reaper")
    stage_watch_monitor.start()
    try:
        ThreadingHTTPServer((SERVICE_HOST, SERVICE_PORT), Handler).serve_forever()
    finally:
        SERVICE_SHUTTING_DOWN.set()
        with PROJECT_STAGE_CONDITION:
            PROJECT_STAGE_CONDITION.notify_all()
        IMAGE_WATCHDOG_STOP.set()
        TEXT_WATCHDOG_STOP.set()
        _shutdown_text_jobs()
        _shutdown_image_jobs()
        _shutdown_video_jobs()
        VIDEO_MEMORY_MONITOR_STOP.set()
        WORKER_HEARTBEAT_STOP.set()
        WORKLOAD_ROUTER.remove(WORKER_ID, generation=1)
        WORKER_REGISTRY.remove(WORKER_ID, generation=1)


if __name__ == "__main__":
    main()
