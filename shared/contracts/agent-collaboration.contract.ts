import type { ContractVersion, Identifier, IsoTimestamp, JsonValue } from "./domain.contract";

export const collaborationSessionStatuses = [
  "active", "paused", "waiting_inspection", "waiting_remediation", "waiting_human",
  "completed", "failed", "cancelled",
] as const;
export type CollaborationSessionStatus = typeof collaborationSessionStatuses[number];

export const handoffTypes = [
  "submit_for_inspection", "remediation_assigned", "resubmit_for_inspection", "manual_takeover",
] as const;
export type HandoffType = typeof handoffTypes[number];

export const handoffStatuses = ["pending", "accepted", "completed", "failed", "cancelled"] as const;
export type HandoffStatus = typeof handoffStatuses[number];

export const evidenceKinds = ["file", "test", "log", "artifact"] as const;
export type EvidenceKind = typeof evidenceKinds[number];

export interface CollaborationEvidenceContract {
  evidence_id: Identifier;
  kind: EvidenceKind;
  reference: string;
  sha256?: string;
  metadata: Record<string, JsonValue>;
}

export interface CollaborationSessionContract {
  session_id: Identifier;
  tenant_id: Identifier;
  project_id: Identifier;
  root_task_id: Identifier;
  developer_agent_id: Identifier;
  inspector_agent_id: Identifier;
  status: CollaborationSessionStatus;
  remediation_round: number;
  max_remediation_rounds: number;
  created_at: IsoTimestamp;
  updated_at: IsoTimestamp;
  contract_version: ContractVersion;
}

export interface TaskHandoffContract {
  handoff_id: Identifier;
  session_id: Identifier;
  task_id: Identifier;
  source_agent_id: Identifier;
  target_agent_id: Identifier;
  handoff_type: HandoffType;
  status: HandoffStatus;
  context_reference: string;
  evidence: CollaborationEvidenceContract[];
  created_at: IsoTimestamp;
  contract_version: ContractVersion;
}

export const inspectionVerdicts = ["passed", "changes_required", "blocked"] as const;
export type InspectionVerdict = typeof inspectionVerdicts[number];

export const inspectionIssueSeverities = ["blocker", "high", "medium", "low"] as const;
export type InspectionIssueSeverity = typeof inspectionIssueSeverities[number];

export interface InspectionIssueContract {
  issue_id: Identifier;
  code: string;
  title: string;
  description: string;
  severity: InspectionIssueSeverity;
  file_reference?: string;
  evidence_ids: Identifier[];
}

export interface InspectionReportContract {
  report_id: Identifier;
  session_id: Identifier;
  handoff_id: Identifier;
  inspector_agent_id: Identifier;
  read_only: true;
  verdict: InspectionVerdict;
  issues: InspectionIssueContract[];
  evidence: CollaborationEvidenceContract[];
  created_at: IsoTimestamp;
  contract_version: ContractVersion;
}

export const remediationInstructionStatuses = ["pending", "running", "completed", "failed", "cancelled"] as const;
export type RemediationInstructionStatus = typeof remediationInstructionStatuses[number];

export interface RemediationInstructionContract {
  instruction_id: Identifier;
  session_id: Identifier;
  report_id: Identifier;
  developer_agent_id: Identifier;
  root_task_id: Identifier;
  issue_ids: Identifier[];
  remediation_round: number;
  status: RemediationInstructionStatus;
  created_at: IsoTimestamp;
  contract_version: ContractVersion;
}
