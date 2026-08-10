import {
  CONTRACT_VERSION,
  type AssetContract,
  type AuthorizationContract,
  type ErrorContract,
  type EventContract,
  type IdentityContract,
  type HumanGateContract,
  type IdempotencyContract,
  type PluginContract,
  type PluginManifestContract,
  type PluginTransitionContract,
  type ProjectContract,
  type TaskContract,
  type TaskTransitionContract,
  type TenantContract,
} from "../../shared/contracts";

const timestamp = "2026-08-07T12:00:00Z";

const identity: IdentityContract = {
  identity_id: "identity-1",
  identity_kind: "user",
  display_name: "Owner",
  is_active: true,
  created_at: timestamp,
  contract_version: CONTRACT_VERSION,
};

const tenant: TenantContract = {
  tenant_id: "tenant-default",
  name: "Default",
  status: "active",
  created_at: timestamp,
  contract_version: CONTRACT_VERSION,
};

const authorization: AuthorizationContract = {
  request_id: "request-1",
  identity_id: identity.identity_id,
  tenant_id: tenant.tenant_id,
  action: "project.read",
  scope_kind: "project",
  scope_id: "project-1",
  decision: "allowed",
  evaluated_at: timestamp,
  contract_version: CONTRACT_VERSION,
};

const project: ProjectContract = {
  project_id: "project-1",
  tenant_id: tenant.tenant_id,
  owner_identity_id: identity.identity_id,
  name: "Project",
  status: "active",
  created_at: timestamp,
  updated_at: timestamp,
  contract_version: CONTRACT_VERSION,
};

const task: TaskContract = {
  task_id: "task-1",
  tenant_id: tenant.tenant_id,
  project_id: project.project_id,
  operation_key: "create-project-1",
  task_type: "contract_test",
  status: "waiting_human",
  progress_percent: 50,
  created_at: timestamp,
  updated_at: timestamp,
  contract_version: CONTRACT_VERSION,
};

const transition: TaskTransitionContract = {
  task_id: task.task_id,
  tenant_id: task.tenant_id,
  project_id: task.project_id,
  transition: "running:waiting_human",
  request_id: "request-2",
  operation_key: "pause-for-review",
  actor_identity_id: identity.identity_id,
  occurred_at: timestamp,
  contract_version: CONTRACT_VERSION,
};

const idempotency: IdempotencyContract = {
  request_id: "request-2",
  operation_key: "pause-for-review",
  request_fingerprint: "a".repeat(64),
  outcome: "accepted",
  task_id: task.task_id,
  evaluated_at: timestamp,
  contract_version: CONTRACT_VERSION,
};

const humanGate: HumanGateContract = {
  gate_id: "gate-1",
  task_id: task.task_id,
  tenant_id: task.tenant_id,
  project_id: task.project_id,
  gate_type: "content_review",
  status: "pending",
  created_at: timestamp,
  contract_version: CONTRACT_VERSION,
};

const plugin: PluginContract = {
  plugin_id: "short_drama",
  name: "Short Drama",
  version: "1.0.0",
  source: "builtin",
  status: "discovered",
  compatible_platform_versions: ["1.0"],
  required_permissions: [],
  contract_version: CONTRACT_VERSION,
};

const pluginManifest: PluginManifestContract = {
  plugin_id: "short_drama", name: "Short Drama", version: "1.0.0", platform_version_range: ">=1.0 <2.0",
  provider: "Yingxu", source: "builtin", capabilities: ["script.write"], permissions: ["model.invoke"],
  dependencies: [{ capability: "image.generate", kind: "replaceable_input" }], data_scopes: ["project.assets"],
  frontend_slots: ["workspace.preview"], backend_entry: "backend/main.py", migration_entry: "migrations/main.py",
  uninstall_policy: "retain", integrity_hash: `sha256:${"a".repeat(64)}`, contract_version: CONTRACT_VERSION,
};

const pluginTransition: PluginTransitionContract = {
  plugin_id: plugin.plugin_id, transition: "installed:enabled", request_id: "request-3",
  operation_key: "enable-short-drama", actor_identity_id: identity.identity_id,
  occurred_at: timestamp, contract_version: CONTRACT_VERSION,
};

const asset: AssetContract = {
  asset_id: "asset-1",
  tenant_id: tenant.tenant_id,
  project_id: project.project_id,
  task_id: task.task_id,
  asset_type: "script",
  status: "available",
  storage_key: "projects/project-1/script.json",
  media_type: "application/json",
  byte_size: 128,
  checksum_sha256: "a".repeat(64),
  created_at: timestamp,
  contract_version: CONTRACT_VERSION,
};

const event: EventContract = {
  event_id: "event-1",
  event_type: "TASK_STATUS_CHANGED",
  occurred_at: timestamp,
  request_id: "request-1",
  trace_id: "trace-1",
  tenant_id: tenant.tenant_id,
  project_id: project.project_id,
  actor_identity_id: identity.identity_id,
  payload: { task_id: task.task_id, previous_status: "running", current_status: task.status },
  contract_version: CONTRACT_VERSION,
};

const error: ErrorContract = {
  code: 409,
  msg: "conflict",
  data: { request_id: "request-1", error_code: "OPERATION_CONFLICT", details: {} },
  timestamp: Date.now(),
};

void [identity, authorization, tenant, project, task, transition, idempotency, humanGate, plugin, pluginManifest, pluginTransition, asset, event, error];

// @ts-expect-error contract statuses are closed enumerations
const invalidTask: TaskContract = { ...task, status: "successful" };
void invalidTask;

// @ts-expect-error denied decisions must include a closed denial reason
const invalidAuthorization: AuthorizationContract = { ...authorization, decision: "denied" };
void invalidAuthorization;

// @ts-expect-error pending gates cannot contain a human decision
const invalidGate: HumanGateContract = { ...humanGate, decided_at: timestamp };
void invalidGate;
