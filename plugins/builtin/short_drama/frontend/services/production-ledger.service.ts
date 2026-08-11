import { postJson, requestJsonOk } from "./api-client";

export type ProductionScopeType = "project" | "story_arc_batch" | "episode_batch" | "episode" | "scene" | "shot" | "line" | "asset";
export type ConfirmationScope = { scope_type:ProductionScopeType; scope_ids:string[] };
export type ImpactScope = Array<{ stage:string; scope_type:ProductionScopeType; scope_id:string }>;
export type ProductionLifecycle = "idle" | "queued" | "running" | "pending_confirmation" | "completed" | "paused" | "failed" | "stale" | "skipped" | "cancelled";
export type ProductionScopeIdentity = { tenant_id:string; user_id:string; project_id:string };
export type ProductionScopeKey = { stage:string; scope_type:ProductionScopeType; scope_id:string };
export type ProductionScopeRecord = ProductionScopeIdentity & ProductionScopeKey & {
  id:string; plugin_key:string; lifecycle:ProductionLifecycle; stage_substate:string;
  content_fingerprint:string; audit_batch_id:string;
  generation:number; revision:number;
  confirmation:null | { content_fingerprint:string; audit_batch_id:string; confirmed_by:string; confirmed_at:string };
  progress:{ completed:number; total:number; [key:string]:unknown };
  production_evidence?:unknown; audit_evidence?:unknown;
  checkpoint:string; error:string; created_at:string; updated_at:string;
  confirmation_scope:ConfirmationScope; impact_scope:ImpactScope;
};
export type ProductionWorkflowState = {
  thread_id:string; status:string; current_stage:string; next_stage:string; stages:Record<string,string>;
  decision:{ action?:string; stage?:string; reason?:string }; updated_at:string; orchestrator:"langgraph"; director_model:string;
};
export type ProductionCapability = { capability:string; provider_id:string; enabled:boolean; metadata:Record<string,unknown> };
export type ProductionExtension = { extension_point:string; provider_id:string; enabled:boolean; metadata:Record<string,unknown> };

export const productionLedgerService = {
  list(identity:ProductionScopeIdentity) {
    return requestJsonOk<{ records:ProductionScopeRecord[] }>(`/api/production/scopes?${new URLSearchParams(identity)}`, { cache:"no-store" }, "生产范围状态加载失败");
  },
  upsert(payload:ProductionScopeIdentity & ProductionScopeKey & Partial<ProductionScopeRecord> & { reactivate?:boolean }) {
    return postJson<{ record:ProductionScopeRecord }>("/api/production/scopes", payload, {}, "生产范围状态保存失败");
  },
  upsertMany(records:Array<ProductionScopeIdentity & ProductionScopeKey & Partial<ProductionScopeRecord> & { reactivate?:boolean }>, replaceBatchScopeSets = false) {
    return postJson<{ records:ProductionScopeRecord[] }>("/api/production/scopes/bulk", { records, replace_batch_scope_sets:replaceBatchScopeSets }, {}, "生产范围状态批量保存失败");
  },
  confirm(payload:ProductionScopeIdentity & ProductionScopeKey & { content_fingerprint?:string; audit_batch_id?:string; generation?:number }) {
    return postJson<{ record:ProductionScopeRecord }>("/api/production/scopes/confirm", payload, {}, "生产范围确认失败");
  },
  confirmAsset(payload:ProductionScopeIdentity & { scope_id:string; phase:"baseline" | "details"; production_evidence?:string[] }) {
    return postJson<{ record:ProductionScopeRecord }>("/api/production/assets/confirm", payload, {}, "人物资产阶段确认失败");
  },
  confirmEpisodeBatch(payload:ProductionScopeIdentity & { stage:string; scope_ids:string[]; rejected_scope_ids?:string[]; rejection_reason?:string; final_batch?:boolean }) {
    return postJson<{ records:ProductionScopeRecord[] }>("/api/production/episode-batches/confirm", payload, {}, "媒体批次确认失败");
  },
  dependency(payload:ProductionScopeIdentity & { source:ProductionScopeKey; target:ProductionScopeKey }) {
    return postJson("/api/production/dependencies", payload, {}, "生产依赖保存失败");
  },
  dependencies(dependencies:Array<ProductionScopeIdentity & { source:ProductionScopeKey; target:ProductionScopeKey }>) {
    return postJson("/api/production/dependencies/bulk", { dependencies }, {}, "生产依赖批量保存失败");
  },
  invalidate(payload:ProductionScopeIdentity & { source:ProductionScopeKey; change_type:string; reason?:string }) {
    return postJson<{ records:ProductionScopeRecord[] }>("/api/production/invalidate", payload, {}, "生产范围失效失败");
  },
  previewImpact(payload:ProductionScopeIdentity & { source:ProductionScopeKey; change_type:string }) {
    return postJson<{ records:ProductionScopeRecord[] }>("/api/production/impact-preview", payload, {}, "生产影响范围读取失败");
  },
  versions(payload:ProductionScopeIdentity) {
    return requestJsonOk<{ versions:Array<ProductionScopeRecord & { version_status:string; versioned_at:string }> }>(`/api/production/versions?${new URLSearchParams(payload)}`, { cache:"no-store" }, "历史版本读取失败");
  },
  workflow(payload:ProductionScopeIdentity) {
    return requestJsonOk<{ workflow:ProductionWorkflowState }>(`/api/production/workflow?${new URLSearchParams(payload)}`, { cache:"no-store" }, "统一编排状态加载失败");
  },
  capabilities() {
    return requestJsonOk<{ capabilities:ProductionCapability[]; extensions:ProductionExtension[] }>("/api/production/capabilities", { cache:"no-store" }, "生产能力加载失败");
  },
  runStage<T>(payload:ProductionScopeIdentity & { stage:string; context:Record<string, unknown>; [key:string]:unknown }, signal?:AbortSignal) {
    return postJson<{ result:T; workflow:ProductionWorkflowState }>("/api/production/run-stage", payload, { signal }, "服务端生产阶段执行失败");
  },
  stopStage(payload:ProductionScopeIdentity & { stage:string }) {
    return postJson<{ stopped:boolean; stage_cancelled:boolean }>("/api/generation/stop", payload, {}, "服务端生产阶段停止失败");
  },
  withdrawConfirmation(payload:ProductionScopeIdentity & ProductionScopeKey & { user_confirmed:true; reason?:string }) {
    return postJson<{ records:ProductionScopeRecord[] }>("/api/production/confirmations/withdraw", payload, {}, "撤回确认失败");
  },
};
