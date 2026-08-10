export interface AgentApiContext {
  requestId: string; traceId: string; identityId: string;
  identityKind: "user" | "service" | "agent"; tenantId: string;
}
export interface AgentSummary { agent_id: string; skill_id: string; name: string; status: string }
export interface ModelSummary { model_id: string; provider_id: string; display_name: string; capabilities: string[]; enabled: boolean; context_window: number }
export interface AgentConfiguration { configuration_id: string; configuration_version: number; agent_id: string; skill_id: string; role: "developer" | "inspector"; model_id: string; settings: Record<string, unknown>; writable: boolean }
export interface ConversationSession { session_id: string; agent_id: string; configuration_version: number; context?: Record<string, unknown> }
export interface ConversationMessage { message_id: string; role: string; content: string; created_at: string }
export interface ConversationProposal { proposal_id: string; proposal_type: "configuration_change" | "task_execution"; status: string; requested_changes: Record<string, unknown>; requires_confirmation: boolean; applied_result?: Record<string, unknown> | null }

export class AgentConfigurationService {
  constructor(private readonly context: AgentApiContext, private readonly baseUrl = "") {}

  registerAgent(skillId: string) { return this.request<AgentSummary>("/api/v1/agents/register", "POST", { skill_id: skillId }); }
  listModels() { return this.request<{ items: ModelSummary[] }>("/api/v1/models"); }
  registerModel(input: { model_id: string; provider_id: string; display_name: string; context_window: number; capabilities: string[] }) {
    return this.request<ModelSummary & { replayed: boolean }>("/api/v1/models/register", "POST", input);
  }
  createConfiguration(agentId: string, modelId: string) {
    return this.request<AgentConfiguration>("/api/v1/agent-configurations", "POST", { agent_id: agentId, model_id: modelId });
  }
  getConfiguration(agentId: string) {
    return this.request<AgentConfiguration>(`/api/v1/agent-configurations/${encodeURIComponent(agentId)}`);
  }
  updateConfiguration(configuration: AgentConfiguration, modelId: string) {
    return this.request<AgentConfiguration>(`/api/v1/agent-configurations/${encodeURIComponent(configuration.agent_id)}/update`, "POST", { expected_version: configuration.configuration_version, model_id: modelId });
  }
  openConversation(agentId: string, context: Record<string, unknown> = {}) { return this.request<ConversationSession>("/api/v1/agent-conversations", "POST", { agent_id: agentId, context }); }
  sendMessage(sessionId: string, content: string) {
    return this.request<{ message: ConversationMessage; proposal: ConversationProposal | null }>(`/api/v1/agent-conversations/${encodeURIComponent(sessionId)}/messages`, "POST", { content });
  }
  getConversation(sessionId: string) {
    return this.request<{ messages: ConversationMessage[]; proposals: ConversationProposal[] }>(`/api/v1/agent-conversations/${encodeURIComponent(sessionId)}`);
  }
  confirmProposal(proposalId: string) { return this.request<ConversationProposal>(`/api/v1/agent-proposals/${encodeURIComponent(proposalId)}/confirm`, "POST", {}); }
  rejectProposal(proposalId: string) { return this.request<ConversationProposal>(`/api/v1/agent-proposals/${encodeURIComponent(proposalId)}/reject`, "POST", {}); }

  private async request<T>(path: string, method = "GET", body?: unknown): Promise<T> {
    const response = await fetch(this.baseUrl + path, {
      method,
      headers: { "Content-Type": "application/json", "X-Request-Id": this.context.requestId, "X-Trace-Id": this.context.traceId, "X-Identity-Id": this.context.identityId, "X-Identity-Kind": this.context.identityKind, "X-Tenant-Id": this.context.tenantId },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const envelope = await response.json() as { data: T; msg: string };
    if (!response.ok) throw new Error(envelope.msg || `AGENT_CONFIGURATION_REQUEST_FAILED:${response.status}`);
    return envelope.data;
  }
}
