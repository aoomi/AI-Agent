"""Minimal HTTP process used to verify the platform runtime baseline."""

from __future__ import annotations

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import time
from typing import Any
from urllib.parse import parse_qs, urlparse

from ai_agent_core import (
    AgentCollaborationError, AgentCollaborationService, AgentConfigurationError,
    AgentConfigurationStore, AgentContextStore, AgentConversationService, AgentScheduler,
    ConversationError, ConversationMemoryStore, InspectionExecutor, ModelConversationClient, PlatformConfig, TaskProposalExecutor,
)
from ai_agent_discovery import AgentMapper, AgentRegistry, AgentRegistryError, IndustrySkillRegistry, IndustrySkillRegistryError, PluginLifecycleError, PluginRegistry, SkillRegistry, SkillRegistryError
from ai_agent_events import EventBus
from ai_agent_llm_gateway import ModelDefinition, ModelRegistry, ModelRegistryError
from ai_agent_queue import InMemoryTaskQueue, QueueConflictError, TaskService
from ai_agent_tenant import IdentityContext, IdentityContextError
from ai_agent_adapters import ProviderHealthChecker, ProviderService, ProviderServiceError
from ai_agent_adapters import LangGraphOrchestrator
from ai_agent_core import IndustryWorkflowService, IndustryWorkflowError


def build_health_payload(config: PlatformConfig) -> dict[str, Any]:
    return {
        "status": "healthy",
        "service": "ai-agent-platform",
        "environment": config.environment,
    }


class PlatformRequestHandler(BaseHTTPRequestHandler):
    server_version = "AIAgentPlatform"

    def do_GET(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        parsed = urlparse(self.path); path = parsed.path
        if path == "/health":
            self._write_json(HTTPStatus.OK, build_health_payload(self.server.platform_config))  # type: ignore[attr-defined]
            return
        if path == "/api/v1/models":
            try: self._identity_context()
            except IdentityContextError: self._write_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_identity_context"}); return
            models = self.server.model_registry.list()  # type: ignore[attr-defined]
            self._write_json(HTTPStatus.OK, {"items": [self._model_payload(model) for model in models]}); return
        if path == "/api/v1/providers":
            try: self._identity_context(); items = self.server.provider_service.list()  # type: ignore[attr-defined]
            except IdentityContextError: self._write_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_identity_context"}); return
            self._write_json(HTTPStatus.OK, {"items": [self._provider_payload(item) for item in items]}); return
        if path == "/api/v1/plugins":
            try: self._identity_context(); items = self.server.plugin_registry.list()  # type: ignore[attr-defined]
            except IdentityContextError: self._write_json(HTTPStatus.BAD_REQUEST, {"error":"invalid_identity_context"}); return
            self._write_json(HTTPStatus.OK, {"items":[self._plugin_payload(item) for item in items]}); return
        if path == "/api/v1/industry-skills":
            try: self._identity_context(); items=self.server.industry_skill_registry.scan()  # type: ignore[attr-defined]
            except (IdentityContextError,IndustrySkillRegistryError): self._write_json(HTTPStatus.BAD_REQUEST,{"error":"industry_skill_scan_failed"}); return
            self._write_json(HTTPStatus.OK,{"items":[{"skill_id":x.skill_id,"name":x.name,"industry_id":x.industry_id,"process_id":x.process_id,"required_capabilities":sorted(x.required_capabilities)} for x in items]}); return
        configuration_prefix = "/api/v1/agent-configurations/"
        if path.startswith(configuration_prefix):
            try:
                self._identity_context(); tail = path[len(configuration_prefix):]
                if tail.endswith("/history"):
                    items = self.server.agent_configurations.history(tail[:-8])  # type: ignore[attr-defined]
                    self._write_json(HTTPStatus.OK, {"items": [self._configuration_payload(item) for item in items]}); return
                version_raw = parse_qs(parsed.query).get("version", [None])[0]
                item = self.server.agent_configurations.get(tail, int(version_raw) if version_raw else None)  # type: ignore[attr-defined]
                self._write_json(HTTPStatus.OK, self._configuration_payload(item)); return
            except IdentityContextError:
                self._write_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_identity_context"}); return
            except (AgentConfigurationError, ValueError):
                self._write_json(HTTPStatus.NOT_FOUND, {"error": "agent_configuration_not_found"}); return
        conversation_prefix = "/api/v1/agent-conversations/"
        if path.startswith(conversation_prefix) and "/" not in path[len(conversation_prefix):]:
            try:
                self._identity_context(); session_id = path[len(conversation_prefix):]
                service = self.server.agent_conversations  # type: ignore[attr-defined]
                self._write_json(HTTPStatus.OK, {
                    "messages": [self._message_payload(item) for item in service.messages(session_id)],
                    "proposals": [self._proposal_payload(item) for item in service.proposals(session_id)],
                }); return
            except IdentityContextError:
                self._write_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_identity_context"}); return
            except ConversationError:
                self._write_json(HTTPStatus.NOT_FOUND, {"error": "conversation_not_found"}); return
        collaboration_prefix = "/api/v1/agent-collaborations/"
        if path.startswith(collaboration_prefix):
            try:
                self._identity_context(); tail = path[len(collaboration_prefix):]; service = self.server.agent_collaborations  # type: ignore[attr-defined]
                if "/" not in tail: item = service.get_session(tail)
                else:
                    session_id, resource = tail.split("/", 1)
                    if resource == "handoffs": item = {"items": [self._collaboration_payload(value) for value in service.handoffs(session_id)]}
                    elif resource == "reports": item = {"items": [self._collaboration_payload(value) for value in service.reports(session_id)]}
                    elif resource == "remediations": item = {"items": [self._collaboration_payload(value) for value in service.instructions(session_id)]}
                    else: raise AgentCollaborationError("unknown collaboration resource")
                self._write_json(HTTPStatus.OK, item if isinstance(item, dict) else self._collaboration_payload(item)); return
            except IdentityContextError: self._write_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_identity_context"}); return
            except AgentCollaborationError: self._write_json(HTTPStatus.NOT_FOUND, {"error": "collaboration_not_found"}); return
        prefix = "/api/v1/agents/"
        if path.startswith(prefix) and path != prefix:
            try:
                self._identity_context()
                agent = self.server.agent_registry.get(path[len(prefix):])  # type: ignore[attr-defined]
            except IdentityContextError:
                self._write_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_identity_context"}); return
            except AgentRegistryError:
                self._write_json(HTTPStatus.NOT_FOUND, {"error": "agent_not_found"})
                return
            self._write_json(HTTPStatus.OK, self._agent_payload(agent))
            return
        if path == "/api/v1/tasks":
            try:
                context = self._identity_context()
                project_id = parse_qs(parsed.query).get("project_id", [None])[0]
                tasks = self.server.task_service.list_tasks(context, project_id)  # type: ignore[attr-defined]
            except (IdentityContextError, ValueError):
                self._write_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_identity_context"}); return
            self._write_json(HTTPStatus.OK, {"items": [self._task_payload(task) for task in tasks]}); return
        task_prefix = "/api/v1/tasks/"
        if path.startswith(task_prefix) and "/" not in path[len(task_prefix):]:
            try: task = self.server.task_service.get_task(self._identity_context(), path[len(task_prefix):])  # type: ignore[attr-defined]
            except (IdentityContextError, QueueConflictError):
                self._write_json(HTTPStatus.NOT_FOUND, {"error": "task_not_found"}); return
            self._write_json(HTTPStatus.OK, self._task_payload(task)); return
        self._write_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        path = urlparse(self.path).path
        if self._handle_management_post(path): return
        task_prefix = "/api/v1/tasks/"
        if path.startswith(task_prefix) and path.endswith(("/cancel", "/resume")):
            tail = path[len(task_prefix):]; task_id, action = tail.rsplit("/", 1)
            try:
                service = self.server.task_service  # type: ignore[attr-defined]
                task = service.cancel_task(self._identity_context(), task_id) if action == "cancel" else service.resume_task(self._identity_context(), task_id)
            except (IdentityContextError, QueueConflictError):
                self._write_json(HTTPStatus.CONFLICT, {"error": "task_transition_rejected"}); return
            self._write_json(HTTPStatus.OK, self._task_payload(task)); return
        if path != "/api/v1/agents/register":
            self._write_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        try:
            self._identity_context()
            length = int(self.headers.get("Content-Length", "0"))
            if not 1 <= length <= 65536:
                raise ValueError
            body = json.loads(self.rfile.read(length))
            skill_id = body["skill_id"]
            if not isinstance(skill_id, str) or not skill_id.strip():
                raise ValueError
            skills = self.server.skill_registry.scan()  # type: ignore[attr-defined]
            agents = self.server.agent_registry.sync(skills)  # type: ignore[attr-defined]
            for skill, agent in zip(skills, agents, strict=True):
                self.server.agent_mapper.bind(skill, agent)  # type: ignore[attr-defined]
                self.server.agent_conversations.bind(agent, skill)  # type: ignore[attr-defined]
            agent = self.server.agent_registry.for_skill(skill_id.strip())  # type: ignore[attr-defined]
        except (ValueError, KeyError, json.JSONDecodeError, SkillRegistryError, AgentRegistryError, IdentityContextError):
            self._write_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_agent_registration"})
            return
        self._write_json(HTTPStatus.OK, self._agent_payload(agent))

    def _handle_management_post(self, path: str) -> bool:
        managed = path in {"/api/v1/models/register", "/api/v1/providers/register", "/api/v1/plugins/install", "/api/v1/industry-robots/register", "/api/v1/industry-workflows/apply", "/api/v1/agent-configurations", "/api/v1/agent-conversations", "/api/v1/agent-collaborations"} or (path.startswith("/api/v1/providers/") and path.endswith("/test")) or path.startswith("/api/v1/plugins/") or path.startswith("/api/v1/agent-configurations/") or path.startswith("/api/v1/agent-conversations/") or path.startswith("/api/v1/agent-proposals/") or path.startswith("/api/v1/agent-collaborations/") or path.startswith("/api/v1/agent-handoffs/") or path.startswith("/api/v1/inspection-reports/")
        if not managed: return False
        try:
            context = self._identity_context(); body = self._read_body()
            if path == "/api/v1/industry-robots/register":
                self.server.industry_skill_registry.scan()  # type: ignore[attr-defined]
                skill=self.server.industry_skill_registry.get(body["skill_id"])  # type: ignore[attr-defined]
                robot,_=self.server.agent_registry.register_scoped(skill,context.tenant_id,body["project_id"])  # type: ignore[attr-defined]
                self._write_json(HTTPStatus.OK,{"robot_id":robot.agent_id,"skill_id":robot.skill_id,"name":robot.name,"tenant_id":robot.tenant_id,"project_id":robot.project_id,"status":robot.status});return True
            if path == "/api/v1/industry-workflows/apply":
                result=self.server.industry_workflows.execute(None,body,context.identity_id)  # type: ignore[attr-defined]
                self._write_json(HTTPStatus.OK,dict(result));return True
            if path == "/api/v1/plugins/install":
                if self.server.plugin_install_executor is None: raise PluginLifecycleError("verified plugin installer is not configured")  # type: ignore[attr-defined]
                plugin_id, version = self.server.plugin_install_executor(body)  # type: ignore[attr-defined]
                registry = self.server.plugin_registry  # type: ignore[attr-defined]
                item = registry.discover(plugin_id, version); registry.transition(plugin_id,"validated"); item=registry.transition(plugin_id,"installed")
                self._write_json(HTTPStatus.OK,self._plugin_payload(item)); return True
            if path.startswith("/api/v1/plugins/"):
                plugin_id, action = path[len("/api/v1/plugins/"):].rsplit("/",1); registry=self.server.plugin_registry  # type: ignore[attr-defined]
                if action=="upgrade": item=registry.upgrade(plugin_id,body["version"])
                elif action=="rollback": item=registry.rollback(plugin_id)
                else:item=registry.transition(plugin_id,{"enable":"enabled","disable":"disabled","uninstall":"uninstalled"}[action])
                self._write_json(HTTPStatus.OK,self._plugin_payload(item));return True
            if path == "/api/v1/models/register":
                model = ModelDefinition.create(
                    model_id=body["model_id"], provider_id=body["provider_id"], display_name=body["display_name"],
                    capabilities=body["capabilities"], enabled=body.get("enabled", True),
                    context_window=body["context_window"], settings=body.get("settings", {}),
                )
                registered, replayed = self.server.model_registry.register(model)  # type: ignore[attr-defined]
                self._write_json(HTTPStatus.OK, {**self._model_payload(registered), "replayed": replayed}); return True
            if path == "/api/v1/providers/register":
                item = self.server.provider_service.register(provider_id=body["provider_id"], display_name=body["display_name"], kind=body["kind"], endpoint=body["endpoint"], secret_reference=body["secret_reference"], capabilities=tuple(body["capabilities"]), enabled=body.get("enabled", True), timeout_seconds=body.get("timeout_seconds", 60), settings=body.get("settings", {}))  # type: ignore[attr-defined]
                self._write_json(HTTPStatus.OK, self._provider_payload(item)); return True
            if path.startswith("/api/v1/providers/") and path.endswith("/test"):
                item = self.server.provider_service.test_connection(path[len("/api/v1/providers/"):-5])  # type: ignore[attr-defined]
                self._write_json(HTTPStatus.OK, self._provider_health_payload(item)); return True
            if path == "/api/v1/agent-configurations":
                agent = self.server.agent_registry.get(body["agent_id"])  # type: ignore[attr-defined]
                try: skill = self.server.industry_skill_registry.get(agent.skill_id)  # type: ignore[attr-defined]
                except IndustrySkillRegistryError: skill = self.server.skill_registry.get(agent.skill_id)  # type: ignore[attr-defined]
                item = self.server.agent_configurations.create(  # type: ignore[attr-defined]
                    agent=agent, skill=skill, model_id=body["model_id"],
                    updated_by_identity_id=context.identity_id, settings=body.get("settings", {}),
                )
                self._write_json(HTTPStatus.OK, self._configuration_payload(item)); return True
            configuration_prefix = "/api/v1/agent-configurations/"
            if path.startswith(configuration_prefix) and path.endswith("/update"):
                agent_id = path[len(configuration_prefix):-7]
                agent = self.server.agent_registry.get(agent_id)  # type: ignore[attr-defined]
                try: skill = self.server.industry_skill_registry.get(agent.skill_id)  # type: ignore[attr-defined]
                except IndustrySkillRegistryError: skill = self.server.skill_registry.get(agent.skill_id)  # type: ignore[attr-defined]
                item = self.server.agent_configurations.update(  # type: ignore[attr-defined]
                    agent_id, expected_version=body["expected_version"], updated_by_identity_id=context.identity_id,
                    model_id=body.get("model_id"), settings=body.get("settings"), skill=skill, agent=agent,
                )
                self._write_json(HTTPStatus.OK, self._configuration_payload(item)); return True
            if path == "/api/v1/agent-conversations":
                session = self.server.agent_conversations.open_session(body["agent_id"], context.identity_id, body.get("context"))  # type: ignore[attr-defined]
                self._write_json(HTTPStatus.OK, self._session_payload(session)); return True
            if path == "/api/v1/agent-collaborations":
                item = self.server.agent_collaborations.open_session(tenant_id=context.tenant_id, project_id=body["project_id"], root_task_id=body["root_task_id"], developer_agent_id=body["developer_agent_id"], inspector_agent_id=body["inspector_agent_id"], max_remediation_rounds=body.get("max_remediation_rounds", 3))  # type: ignore[attr-defined]
                self._write_json(HTTPStatus.OK, self._collaboration_payload(item)); return True
            if path.startswith("/api/v1/agent-collaborations/") and path.endswith("/handoffs"):
                session_id = path[len("/api/v1/agent-collaborations/"):-9]
                item = self.server.agent_collaborations.submit_for_inspection(session_id, task_id=body["task_id"], context_reference=body["context_reference"], evidence=tuple(body.get("evidence", [])))  # type: ignore[attr-defined]
                self._write_json(HTTPStatus.OK, self._collaboration_payload(item)); return True
            if path.startswith("/api/v1/agent-collaborations/") and path.endswith("/cycles"):
                session_id = path[len("/api/v1/agent-collaborations/"):-7]
                handoff, report, remediation = self.server.agent_collaborations.run_cycle(session_id, task_id=body["task_id"], context_reference=body["context_reference"], evidence=tuple(body.get("evidence", [])))  # type: ignore[attr-defined]
                self._write_json(HTTPStatus.OK, {"handoff":self._collaboration_payload(handoff), "report":self._collaboration_payload(report), "remediation":self._collaboration_payload(remediation) if remediation else None}); return True
            if path.startswith("/api/v1/agent-handoffs/") and path.endswith("/inspect"):
                item = self.server.agent_collaborations.run_inspection(path[len("/api/v1/agent-handoffs/"):-8])  # type: ignore[attr-defined]
                self._write_json(HTTPStatus.OK, self._collaboration_payload(item)); return True
            if path.startswith("/api/v1/inspection-reports/") and path.endswith("/remediation"):
                item = self.server.agent_collaborations.create_remediation(path[len("/api/v1/inspection-reports/"):-12])  # type: ignore[attr-defined]
                self._write_json(HTTPStatus.OK, self._collaboration_payload(item)); return True
            conversation_prefix = "/api/v1/agent-conversations/"
            if path.startswith(conversation_prefix) and path.endswith("/messages"):
                session_id = path[len(conversation_prefix):-9]
                message, proposal = self.server.agent_conversations.send(session_id, body["content"])  # type: ignore[attr-defined]
                self._write_json(HTTPStatus.OK, {"message": self._message_payload(message), "proposal": self._proposal_payload(proposal) if proposal else None}); return True
            proposal_prefix = "/api/v1/agent-proposals/"
            if path.startswith(proposal_prefix) and path.endswith(("/confirm", "/reject")):
                tail = path[len(proposal_prefix):]; proposal_id, action = tail.rsplit("/", 1)
                service = self.server.agent_conversations  # type: ignore[attr-defined]
                proposal = service.confirm(proposal_id, context.identity_id) if action == "confirm" else service.reject(proposal_id)
                self._write_json(HTTPStatus.OK, self._proposal_payload(proposal)); return True
            self._write_json(HTTPStatus.NOT_FOUND, {"error": "not_found"}); return True
        except IdentityContextError:
            self._write_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_identity_context"}); return True
        except (AgentConfigurationError, ConversationError, AgentCollaborationError, ProviderServiceError, PluginLifecycleError, IndustryWorkflowError, IndustrySkillRegistryError):
            self._write_json(HTTPStatus.CONFLICT, {"error": "management_operation_rejected"}); return True
        except (KeyError, TypeError, ValueError, json.JSONDecodeError, ModelRegistryError, AgentRegistryError, SkillRegistryError):
            self._write_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_management_request"}); return True

    def _read_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if not 1 <= length <= 262144: raise ValueError("invalid content length")
        body = json.loads(self.rfile.read(length))
        if not isinstance(body, dict): raise ValueError("body must be an object")
        return body

    @staticmethod
    def _agent_payload(agent: Any) -> dict[str, str]:
        return {"agent_id": agent.agent_id, "skill_id": agent.skill_id, "name": agent.name, "status": agent.status}

    @staticmethod
    def _task_payload(task: Any) -> dict[str, Any]:
        return {"task_id": task.task_id, "project_id": task.project_id, "operation_key": task.operation_key, "task_type": task.task_type, "tenant_id": task.context.tenant_id, "status": task.status, "payload": dict(task.payload)}

    @staticmethod
    def _model_payload(model: Any) -> dict[str, Any]:
        return {"model_id": model.model_id, "provider_id": model.provider_id, "display_name": model.display_name, "capabilities": sorted(model.capabilities), "enabled": model.enabled, "context_window": model.context_window, "contract_version": model.contract_version}

    @staticmethod
    def _provider_payload(item: Any) -> dict[str, Any]:
        return {"provider_id":item.provider_id,"display_name":item.display_name,"kind":item.kind,"endpoint":item.endpoint,"secret_reference":item.secret_reference,"capabilities":list(item.capabilities),"enabled":item.enabled,"timeout_seconds":item.timeout_seconds,"settings":dict(item.settings),"created_at":item.created_at,"updated_at":item.updated_at}

    @staticmethod
    def _provider_health_payload(item: Any) -> dict[str, Any]:
        return {"provider_id":item.provider_id,"status":item.status,"checked_at":item.checked_at,"latency_ms":item.latency_ms,"error_code":item.error_code,"consecutive_failures":item.consecutive_failures}

    @staticmethod
    def _plugin_payload(item: Any) -> dict[str,str]: return {"plugin_id":item.plugin_id,"version":item.version,"status":item.status}

    @staticmethod
    def _configuration_payload(item: Any) -> dict[str, Any]:
        return {"configuration_id": item.configuration_id, "configuration_version": item.configuration_version, "agent_id": item.agent_id, "skill_id": item.skill_id, "role": item.role, "model_id": item.model_id, "system_prompt_version": item.system_prompt_version, "settings": dict(item.settings), "writable": item.writable, "updated_by_identity_id": item.updated_by_identity_id, "updated_at": item.updated_at, "contract_version": item.contract_version}

    @staticmethod
    def _session_payload(item: Any) -> dict[str, Any]:
        return {"session_id": item.session_id, "agent_id": item.agent_id, "configuration_version": item.configuration_version, "created_by_identity_id": item.created_by_identity_id, "created_at": item.created_at, "context": dict(item.context)}

    @staticmethod
    def _message_payload(item: Any) -> dict[str, Any]:
        return {"message_id": item.message_id, "session_id": item.session_id, "agent_id": item.agent_id, "role": item.role, "content": item.content, "created_at": item.created_at, "contract_version": item.contract_version}

    @staticmethod
    def _proposal_payload(item: Any) -> dict[str, Any]:
        return {"proposal_id": item.proposal_id, "session_id": item.session_id, "agent_id": item.agent_id, "proposal_type": item.proposal_type, "status": item.status, "requested_changes": dict(item.requested_changes), "requires_confirmation": item.requires_confirmation, "created_at": item.created_at, "applied_result": dict(item.applied_result) if item.applied_result else None, "contract_version": item.contract_version}

    @staticmethod
    def _collaboration_payload(item: Any) -> dict[str, Any]:
        from dataclasses import fields, is_dataclass
        def convert(value: Any) -> Any:
            if is_dataclass(value): return {field.name: convert(getattr(value, field.name)) for field in fields(value)}
            if isinstance(value, dict) or hasattr(value, "items"): return {key: convert(child) for key, child in value.items()}
            if isinstance(value, (tuple, list)): return [convert(child) for child in value]
            return value
        return convert(item)

    def _identity_context(self) -> IdentityContext:
        return IdentityContext(
            self.headers.get("X-Request-Id", ""), self.headers.get("X-Trace-Id", ""),
            self.headers.get("X-Identity-Id", ""), self.headers.get("X-Identity-Kind", ""),
            self.headers.get("X-Tenant-Id", ""),
        )

    def log_message(self, format: str, *args: object) -> None:
        return

    def _write_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        if status.value < 400:
            envelope = {"code": 200, "msg": "success", "data": payload, "timestamp": int(time.time() * 1000)}
        else:
            raw_error = str(payload.get("error", "internal_error"))
            envelope = {
                "code": status.value, "msg": raw_error.replace("_", " "),
                "data": {"request_id": self.headers.get("X-Request-Id", "unknown"), "error_code": raw_error.upper(), "details": {}},
                "timestamp": int(time.time() * 1000),
            }
        body = json.dumps(envelope, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class PlatformHttpServer(ThreadingHTTPServer):
    platform_config: PlatformConfig


def create_server(
    config: PlatformConfig,
    plugins_root: Path | None = None,
    task_queue: InMemoryTaskQueue | None = None,
    task_events: EventBus | None = None,
    model_registry: ModelRegistry | None = None,
    conversation_model_client: ModelConversationClient | None = None,
    task_proposal_executor: TaskProposalExecutor | None = None,
    inspection_executor: InspectionExecutor | None = None,
    provider_health_checker: ProviderHealthChecker | None = None,
    plugin_install_executor: Any | None = None,
    industry_workflow_executor: TaskProposalExecutor | None = None,
) -> PlatformHttpServer:
    server = PlatformHttpServer((config.host, config.port), PlatformRequestHandler)
    server.platform_config = config
    server.skill_registry = SkillRegistry(plugins_root or Path("plugins/builtin"))  # type: ignore[attr-defined]
    server.industry_skill_registry = IndustrySkillRegistry(plugins_root or Path("plugins"))  # type: ignore[attr-defined]
    server.agent_registry = AgentRegistry()  # type: ignore[attr-defined]
    server.agent_mapper = AgentMapper()  # type: ignore[attr-defined]
    server.plugin_registry = PluginRegistry()  # type: ignore[attr-defined]
    server.plugin_install_executor = plugin_install_executor  # type: ignore[attr-defined]
    server.task_service = TaskService(task_queue or InMemoryTaskQueue(), task_events)  # type: ignore[attr-defined]
    server.model_registry = model_registry or ModelRegistry()  # type: ignore[attr-defined]
    server.provider_service = ProviderService(provider_health_checker)  # type: ignore[attr-defined]
    server.agent_configurations = AgentConfigurationStore(server.model_registry)  # type: ignore[attr-defined]
    server.agent_conversations = AgentConversationService(  # type: ignore[attr-defined]
        server.model_registry, server.agent_configurations,
        conversation_model_client, task_proposal_executor, industry_workflow_executor,
        ConversationMemoryStore(Path("data/conversations/memory.json")),
    )
    server.agent_scheduler = AgentScheduler(server.agent_registry, AgentContextStore())  # type: ignore[attr-defined]
    server.agent_collaborations = AgentCollaborationService(server.agent_configurations, inspection_executor, server.agent_scheduler)  # type: ignore[attr-defined]
    server.industry_workflows = industry_workflow_executor or IndustryWorkflowService(LangGraphOrchestrator())  # type: ignore[attr-defined]
    return server
