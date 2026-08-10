import type { ContractVersion, Identifier, IsoTimestamp, JsonValue } from "./domain.contract";

export const agentRoles = ["developer", "inspector"] as const;
export type AgentRole = typeof agentRoles[number];

export const modelCapabilities = ["chat", "reasoning", "tool_calling", "vision", "structured_output"] as const;
export type ModelCapability = typeof modelCapabilities[number];

export interface ModelDefinitionContract {
  model_id: Identifier;
  provider_id: Identifier;
  display_name: string;
  capabilities: ModelCapability[];
  enabled: boolean;
  context_window: number;
  contract_version: ContractVersion;
}

export interface AgentConfigurationContract {
  configuration_id: Identifier;
  configuration_version: number;
  agent_id: Identifier;
  skill_id: Identifier;
  role: AgentRole;
  model_id: Identifier;
  system_prompt_version: string;
  settings: Record<string, JsonValue>;
  writable: boolean;
  updated_by_identity_id: Identifier;
  updated_at: IsoTimestamp;
  contract_version: ContractVersion;
}

export const conversationMessageRoles = ["user", "assistant", "system", "tool"] as const;
export type ConversationMessageRole = typeof conversationMessageRoles[number];

export interface AgentConversationMessageContract {
  message_id: Identifier;
  session_id: Identifier;
  agent_id: Identifier;
  role: ConversationMessageRole;
  content: string;
  created_at: IsoTimestamp;
  contract_version: ContractVersion;
}

export const proposalStatuses = ["draft", "pending_confirmation", "applied", "rejected", "failed"] as const;
export type ProposalStatus = typeof proposalStatuses[number];

export interface ConversationProposalContract {
  proposal_id: Identifier;
  session_id: Identifier;
  agent_id: Identifier;
  proposal_type: "configuration_change" | "task_execution" | "industry_workflow";
  status: ProposalStatus;
  requested_changes: Record<string, JsonValue>;
  requires_confirmation: boolean;
  created_at: IsoTimestamp;
  contract_version: ContractVersion;
}
