import type { ContractVersion, Identifier, IsoTimestamp, JsonValue } from "./domain.contract";

export const providerKinds = ["model", "text", "image", "video", "audio"] as const;
export type ProviderKind = typeof providerKinds[number];
export const providerHealthStatuses = ["unknown", "healthy", "degraded", "unhealthy", "disabled"] as const;
export type ProviderHealthStatus = typeof providerHealthStatuses[number];

export interface ProviderRateLimitContract {
  requests_per_minute: number;
  concurrent_requests: number;
}

export interface ProviderConfigurationContract {
  provider_id: Identifier;
  display_name: string;
  kind: ProviderKind;
  endpoint: string;
  secret_reference: string;
  capabilities: string[];
  enabled: boolean;
  timeout_seconds: number;
  rate_limit: ProviderRateLimitContract;
  settings: Record<string, JsonValue>;
  created_at: IsoTimestamp;
  updated_at: IsoTimestamp;
  contract_version: ContractVersion;
}

export interface ProviderHealthContract {
  provider_id: Identifier;
  status: ProviderHealthStatus;
  checked_at: IsoTimestamp;
  latency_ms: number | null;
  error_code: string | null;
  consecutive_failures: number;
  circuit_open_until: IsoTimestamp | null;
  contract_version: ContractVersion;
}
