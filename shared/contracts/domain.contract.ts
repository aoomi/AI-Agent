/**
 * Cross-layer V1 contract baseline.
 *
 * These structures describe identity and scope only. They do not imply that
 * persistence, HTTP endpoints, queues, or plugin loading are implemented.
 */

export type Identifier = string;
export type IsoTimestamp = string;
export type JsonScalar = boolean | number | string;
export type JsonValue = JsonScalar | JsonValue[] | { [key: string]: JsonValue };
export type ContractVersion = "1.0";

export const CONTRACT_VERSION: ContractVersion = "1.0";

export const identityKinds = ["user", "service", "agent"] as const;
export type IdentityKind = typeof identityKinds[number];

export interface IdentityContract {
  identity_id: Identifier;
  identity_kind: IdentityKind;
  display_name: string;
  is_active: boolean;
  created_at: IsoTimestamp;
  contract_version: ContractVersion;
}

export const authorizationActions = [
  "identity.read",
  "project.read",
  "project.write",
  "task.read",
  "task.execute",
  "task.cancel",
  "plugin.read",
  "plugin.enable",
  "plugin.execute",
  "asset.read",
  "asset.write",
  "asset.export",
] as const;
export type AuthorizationAction = typeof authorizationActions[number];

export const authorizationScopeKinds = ["identity", "project", "tenant", "platform"] as const;
export type AuthorizationScopeKind = typeof authorizationScopeKinds[number];

export const authorizationDenialReasons = [
  "UNAUTHENTICATED",
  "INACTIVE_IDENTITY",
  "PERMISSION_MISSING",
  "SCOPE_MISMATCH",
  "TENANT_MISMATCH",
  "RESOURCE_NOT_FOUND",
  "PLUGIN_DISABLED",
] as const;
export type AuthorizationDenialReason = typeof authorizationDenialReasons[number];

interface AuthorizationBaseContract {
  request_id: Identifier;
  identity_id: Identifier;
  tenant_id: Identifier;
  action: AuthorizationAction;
  scope_kind: AuthorizationScopeKind;
  scope_id: Identifier;
  evaluated_at: IsoTimestamp;
  contract_version: ContractVersion;
}

export interface AuthorizationAllowedContract extends AuthorizationBaseContract {
  decision: "allowed";
  denial_reason?: never;
}

export interface AuthorizationDeniedContract extends AuthorizationBaseContract {
  decision: "denied";
  denial_reason: AuthorizationDenialReason;
}

export type AuthorizationContract = AuthorizationAllowedContract | AuthorizationDeniedContract;

export const tenantStatuses = ["inactive", "active", "suspended"] as const;
export type TenantStatus = typeof tenantStatuses[number];

/** V1/V2 use a stable default tenant scope; SaaS isolation is enabled in V3. */
export interface TenantContract {
  tenant_id: Identifier;
  name: string;
  status: TenantStatus;
  created_at: IsoTimestamp;
  contract_version: ContractVersion;
}

export const projectStatuses = ["draft", "active", "archived"] as const;
export type ProjectStatus = typeof projectStatuses[number];

export interface ProjectContract {
  project_id: Identifier;
  tenant_id: Identifier;
  owner_identity_id: Identifier;
  name: string;
  status: ProjectStatus;
  created_at: IsoTimestamp;
  updated_at: IsoTimestamp;
  contract_version: ContractVersion;
}

export const projectStateTransitions = [
  "draft:active",
  "draft:archived",
  "active:archived",
  "archived:active",
] as const;
export type ProjectStateTransition = typeof projectStateTransitions[number];

export interface ProjectTransitionContract {
  project_id: Identifier;
  tenant_id: Identifier;
  transition: ProjectStateTransition;
  request_id: Identifier;
  operation_key: string;
  actor_identity_id: Identifier;
  occurred_at: IsoTimestamp;
  contract_version: ContractVersion;
}

export const taskStatuses = [
  "queued",
  "running",
  "waiting_human",
  "paused",
  "completed",
  "failed",
  "cancelled",
] as const;
export type TaskStatus = typeof taskStatuses[number];

export interface TaskContract {
  task_id: Identifier;
  tenant_id: Identifier;
  project_id: Identifier;
  operation_key: string;
  task_type: string;
  status: TaskStatus;
  progress_percent: number;
  created_at: IsoTimestamp;
  updated_at: IsoTimestamp;
  contract_version: ContractVersion;
}

export const taskStateTransitions = [
  "queued:running",
  "queued:cancelled",
  "running:waiting_human",
  "running:paused",
  "running:completed",
  "running:failed",
  "running:cancelled",
  "waiting_human:running",
  "waiting_human:cancelled",
  "paused:queued",
  "paused:cancelled",
  "failed:queued",
  "failed:cancelled",
] as const;
export type TaskStateTransition = typeof taskStateTransitions[number];

export interface TaskTransitionContract {
  task_id: Identifier;
  tenant_id: Identifier;
  project_id: Identifier;
  transition: TaskStateTransition;
  request_id: Identifier;
  operation_key: string;
  actor_identity_id: Identifier;
  occurred_at: IsoTimestamp;
  contract_version: ContractVersion;
}

export const idempotencyOutcomes = ["accepted", "replayed", "conflict"] as const;
export type IdempotencyOutcome = typeof idempotencyOutcomes[number];

interface IdempotencyBaseContract {
  request_id: Identifier;
  operation_key: string;
  request_fingerprint: string;
  evaluated_at: IsoTimestamp;
  contract_version: ContractVersion;
}

export interface IdempotencyAcceptedContract extends IdempotencyBaseContract {
  outcome: "accepted";
  task_id: Identifier;
  original_request_id?: never;
}

export interface IdempotencyReplayContract extends IdempotencyBaseContract {
  outcome: "replayed";
  task_id: Identifier;
  original_request_id: Identifier;
}

export interface IdempotencyConflictContract extends IdempotencyBaseContract {
  outcome: "conflict";
  original_request_id: Identifier;
  task_id?: never;
}

export type IdempotencyContract =
  | IdempotencyAcceptedContract
  | IdempotencyReplayContract
  | IdempotencyConflictContract;

interface HumanGateBaseContract {
  gate_id: Identifier;
  task_id: Identifier;
  tenant_id: Identifier;
  project_id: Identifier;
  gate_type: string;
  created_at: IsoTimestamp;
  contract_version: ContractVersion;
}

export interface HumanGatePendingContract extends HumanGateBaseContract {
  status: "pending";
  decided_by_identity_id?: never;
  decided_at?: never;
}

export interface HumanGateResolvedContract extends HumanGateBaseContract {
  status: "approved" | "rejected";
  decided_by_identity_id: Identifier;
  decided_at: IsoTimestamp;
}

export type HumanGateContract = HumanGatePendingContract | HumanGateResolvedContract;

export const pluginStatuses = ["discovered", "validated", "installed", "enabled", "disabled", "failed", "uninstalled"] as const;
export type PluginStatus = typeof pluginStatuses[number];
export const pluginSources = ["builtin", "custom"] as const;
export type PluginSource = typeof pluginSources[number];

export const pluginDependencyKinds = ["required", "replaceable_input", "optional_enhancement"] as const;
export type PluginDependencyKind = typeof pluginDependencyKinds[number];

export const pluginPermissionKinds = [
  "filesystem.read", "filesystem.write", "network.request", "model.invoke",
  "queue.publish", "queue.consume", "secret.read", "tenant_data.read", "tenant_data.write",
] as const;
export type PluginPermissionKind = typeof pluginPermissionKinds[number];

export interface PluginDependencyContract {
  capability: string;
  kind: PluginDependencyKind;
  provider_plugin_id?: Identifier;
}

export interface PluginManifestContract {
  plugin_id: Identifier;
  name: string;
  version: string;
  platform_version_range: string;
  provider: string;
  source: PluginSource;
  capabilities: string[];
  permissions: PluginPermissionKind[];
  dependencies: PluginDependencyContract[];
  data_scopes: string[];
  frontend_slots: string[];
  backend_entry: string;
  migration_entry: string;
  uninstall_policy: "retain" | "export_then_remove";
  integrity_hash: string;
  contract_version: ContractVersion;
}

export const pluginStateTransitions = [
  "discovered:validated", "discovered:failed", "validated:installed", "validated:failed",
  "installed:enabled", "installed:uninstalled", "enabled:disabled", "enabled:failed",
  "disabled:enabled", "disabled:uninstalled", "failed:disabled",
] as const;
export type PluginStateTransition = typeof pluginStateTransitions[number];

export interface PluginTransitionContract {
  plugin_id: Identifier;
  transition: PluginStateTransition;
  request_id: Identifier;
  operation_key: string;
  actor_identity_id: Identifier;
  occurred_at: IsoTimestamp;
  contract_version: ContractVersion;
}

export interface PluginContract {
  plugin_id: Identifier;
  name: string;
  version: string;
  source: PluginSource;
  status: PluginStatus;
  compatible_platform_versions: string[];
  required_permissions: string[];
  contract_version: ContractVersion;
}

export const assetStatuses = ["pending", "available", "invalidated", "failed"] as const;
export type AssetStatus = typeof assetStatuses[number];

export interface AssetContract {
  asset_id: Identifier;
  tenant_id: Identifier;
  project_id: Identifier;
  task_id: Identifier;
  asset_type: string;
  status: AssetStatus;
  storage_key: string;
  media_type: string;
  byte_size: number;
  checksum_sha256: string;
  created_at: IsoTimestamp;
  contract_version: ContractVersion;
}

export interface AssetProvenanceContract {
  provider: string;
  provider_version: string;
  model_id: string;
  model_version: string;
  prompt_version: string;
  source_asset_version_ids: Identifier[];
}

export interface AssetVersionContract {
  asset_version_id: Identifier;
  asset_id: Identifier;
  tenant_id: Identifier;
  project_id: Identifier;
  task_id: Identifier;
  version_number: number;
  parent_asset_version_id: Identifier | "";
  storage_key: string;
  media_type: string;
  byte_size: number;
  checksum_sha256: string;
  provenance: AssetProvenanceContract;
  created_at: IsoTimestamp;
  contract_version: ContractVersion;
}

export const assetInvalidationScopeKinds = ["asset", "episode", "scene", "shot", "dialogue", "time_window"] as const;
export type AssetInvalidationScopeKind = typeof assetInvalidationScopeKinds[number];
export const assetInvalidationReasons = ["UPSTREAM_CHANGED", "HUMAN_REJECTED", "GENERATION_FAILED", "MANUAL_REPLACEMENT"] as const;
export type AssetInvalidationReason = typeof assetInvalidationReasons[number];

export interface AssetInvalidationContract {
  invalidation_id: Identifier;
  tenant_id: Identifier;
  project_id: Identifier;
  scope_kind: AssetInvalidationScopeKind;
  scope_id: Identifier;
  affected_asset_version_ids: Identifier[];
  reason: AssetInvalidationReason;
  preserve_history: true;
  request_id: Identifier;
  actor_identity_id: Identifier;
  invalidated_at: IsoTimestamp;
  contract_version: ContractVersion;
}

export const exportStatuses = ["queued", "running", "completed", "failed", "cancelled"] as const;
export type ExportStatus = typeof exportStatuses[number];

interface AssetExportBaseContract {
  export_id: Identifier;
  tenant_id: Identifier;
  project_id: Identifier;
  task_id: Identifier;
  asset_version_ids: Identifier[];
  export_format: string;
  request_id: Identifier;
  operation_key: string;
  created_at: IsoTimestamp;
  updated_at: IsoTimestamp;
  contract_version: ContractVersion;
}

export interface AssetExportPendingContract extends AssetExportBaseContract {
  status: Exclude<ExportStatus, "completed">;
  output_storage_key: "";
  checksum_sha256: "";
}

export interface AssetExportCompletedContract extends AssetExportBaseContract {
  status: "completed";
  output_storage_key: string;
  checksum_sha256: string;
}

export type AssetExportContract = AssetExportPendingContract | AssetExportCompletedContract;

export interface ContractErrorData {
  request_id: Identifier;
  error_code: ErrorCode;
  details: Record<string, JsonValue>;
}

export const errorCodes = [
  "VALIDATION_ERROR", "UNAUTHENTICATED", "PERMISSION_DENIED", "RESOURCE_NOT_FOUND",
  "OPERATION_CONFLICT", "TASK_TIMEOUT", "DEPENDENCY_UNAVAILABLE", "INTERNAL_ERROR",
] as const;
export type ErrorCode = typeof errorCodes[number];

export interface ApiResponse<TData extends object> {
  code: 200 | 400 | 401 | 403 | 404 | 409 | 500;
  msg: string;
  data: TData;
  timestamp: number;
}

export type ErrorContract = ApiResponse<ContractErrorData>;

export const eventTypes = [
  "PROJECT_CREATED",
  "TASK_STATUS_CHANGED",
  "PLUGIN_STATUS_CHANGED",
  "ASSET_STATUS_CHANGED",
] as const;
export type EventType = typeof eventTypes[number];

interface EventBaseContract {
  event_id: Identifier;
  occurred_at: IsoTimestamp;
  request_id: Identifier;
  trace_id: Identifier;
  tenant_id: Identifier;
  project_id: Identifier;
  actor_identity_id: Identifier;
  contract_version: ContractVersion;
}

export type EventContract = EventBaseContract & (
  | { event_type: "PROJECT_CREATED"; payload: { project_id: Identifier; status: ProjectStatus } }
  | { event_type: "TASK_STATUS_CHANGED"; payload: { task_id: Identifier; previous_status: TaskStatus; current_status: TaskStatus } }
  | { event_type: "PLUGIN_STATUS_CHANGED"; payload: { plugin_id: Identifier; previous_status: PluginStatus; current_status: PluginStatus } }
  | { event_type: "ASSET_STATUS_CHANGED"; payload: { asset_id: Identifier; asset_version_id: Identifier; status: AssetStatus } }
);
