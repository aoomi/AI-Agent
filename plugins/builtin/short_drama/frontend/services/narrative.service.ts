import { postJson, postJsonIgnoringResponse, requestJson, requestJsonOk, type ApiResponseMessages } from "./api-client";

export type NarrativeKind = "outline" | "script" | "storyboard";

export const narrativeService = {
  resume(kind:NarrativeKind) {
    return postJsonIgnoringResponse("/api/generation/resume", { kind });
  },
  stop(kind:NarrativeKind, context:Record<string, unknown> = {}) {
    return postJsonIgnoringResponse("/api/generation/stop", { kind, ...context });
  },
  outlinePlan<T>(body:unknown, signal?:AbortSignal) {
    return postJson<T>("/api/outline/plan", body, { signal }, "全剧规划生成失败");
  },
  outlineEpisodes<T>(body:unknown, signal?:AbortSignal) {
    return requestJson<T>("/api/outline/episodes", { method:"POST", headers:{ "Content-Type":"application/json" }, signal, body:JSON.stringify(body) });
  },
  scriptEpisode<T>(body:unknown, signal?:AbortSignal) {
    return requestJson<T>("/api/script/episode", { method:"POST", headers:{ "Content-Type":"application/json" }, signal, body:JSON.stringify(body) });
  },
  storyboard<T>(body:unknown, signal?:AbortSignal) {
    return requestJson<T>("/api/storyboard", { method:"POST", headers:{ "Content-Type":"application/json" }, signal, body:JSON.stringify(body) });
  },
  storyboardShot<T>(body:unknown, signal?:AbortSignal) {
    return requestJson<T>("/api/storyboard/shot", { method:"POST", headers:{ "Content-Type":"application/json" }, signal, body:JSON.stringify(body) });
  },
  audit<T>(body:unknown, signal:AbortSignal | undefined, messages:ApiResponseMessages) {
    return requestJson<T>("/api/audit/narrative", { method:"POST", headers:{ "Content-Type":"application/json" }, signal, body:JSON.stringify(body) }, messages);
  },
  auditStatus<T>(auditId:string) {
    return requestJsonOk<T>(`/api/audit/status?audit_id=${encodeURIComponent(auditId)}`);
  },
  stopAudit() {
    return postJsonIgnoringResponse("/api/audit/stop", {});
  },
  rewrite<T>(body:unknown, signal?:AbortSignal, fallback = "审核自动修改失败") {
    return postJson<T>("/api/rewrite", body, { signal }, fallback);
  },
};
