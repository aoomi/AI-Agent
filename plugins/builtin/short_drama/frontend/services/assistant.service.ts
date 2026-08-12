import { postJson, requestJsonOk } from "./api-client";

export const assistantService = {
  health<T>() { return requestJsonOk<T>("/api/health", { cache:"no-store" }); },
  queue<T>(identity:{ tenant_id:string; user_id:string; project_id:string }) { return requestJsonOk<T>(`/api/queue/status?${new URLSearchParams(identity)}`, { cache:"no-store" }); },
  rewrite<T>(body:unknown, fallback = "本地模型处理失败") { return postJson<T>("/api/rewrite", body, {}, fallback); },
  memory<T>(body:unknown) { return postJson<T>("/api/memory", body); },
  understand<T>(body:unknown, signal?:AbortSignal) { return postJson<T>("/api/assistant", body, { signal }, "助手理解失败"); },
  runAgent<T>(body:unknown, signal?:AbortSignal) { return postJson<T>("/api/assistant/agents/run", body, { signal }, "系统 AI 执行失败"); },
  startAgent<T>(body:unknown, signal?:AbortSignal) { return postJson<T>("/api/assistant/agents/start", body, { signal }, "系统 AI 任务启动失败"); },
  agentStatus<T>(jobId:string, identity:{ tenant_id:string; user_id:string; project_id:string; session_id:string }, signal?:AbortSignal) { return requestJsonOk<T>(`/api/assistant/agents/status?${new URLSearchParams({ job_id:jobId, ...identity })}`, { cache:"no-store", signal }, "系统 AI 任务状态读取失败"); },
  route<T>(body:unknown, signal?:AbortSignal) { return postJson<T>("/api/assistant/route", body, { signal }, "任务路由失败"); },
  history<T>(body:unknown, signal?:AbortSignal) { return postJson<T>("/api/assistant/history", body, { signal }, "对话记录恢复失败"); },
  saveHistory<T>(body:unknown, signal?:AbortSignal) { return postJson<T>("/api/assistant/history/save", body, { signal }, "对话记录保存失败"); },
  sessions<T>(body:unknown, signal?:AbortSignal) { return postJson<T>("/api/assistant/sessions", body, { signal }, "对话会话读取失败"); },
  draft<T>(body:unknown, signal?:AbortSignal) { return postJson<T>("/api/assistant/draft", body, { signal }, "对话草稿保存失败"); },
  capabilities<T>(signal?:AbortSignal) { return requestJsonOk<T>("/api/assistant/capabilities", { cache:"no-store", signal }, "助手模型与技能读取失败"); },
  operation<T>(body:unknown, signal?:AbortSignal) { return postJson<T>("/api/assistant/operation", body, { signal }, "助手操作失败"); },
  createInvitation<T>(body:unknown, signal?:AbortSignal) { return postJson<T>("/api/invitations", body, { signal }, "邀请链接创建失败"); },
  resolveInvitation<T>(token:string, signal?:AbortSignal) { return requestJsonOk<T>(`/api/invitations?${new URLSearchParams({ token })}`, { cache:"no-store", signal }, "邀请链接读取失败"); },
  revokeInvitation<T>(body:unknown, signal?:AbortSignal) { return postJson<T>("/api/invitations/revoke", body, { signal }, "邀请链接撤销失败"); },
  redeemInvitation<T>(body:unknown, signal?:AbortSignal) { return postJson<T>("/api/invitations/redeem", body, { signal }, "邀请链接使用失败"); },
  vision<T>(body:unknown, signal?:AbortSignal) { return postJson<T>("/api/vision", body, { signal }, "图片或视频识别失败"); },
  imagePlan<T>(body:unknown, signal?:AbortSignal) { return postJson<T>("/api/assistant/image-plan", body, { signal }, "生图需求理解失败"); },
  async transcribe<T>(file:File, signal?:AbortSignal) {
    const response = await fetch("/api/vision/transcribe", { method:"POST", headers:{ "Content-Type":file.type || "application/octet-stream", "X-Filename":encodeURIComponent(file.name) }, body:file, signal });
    const payload = await response.json().catch(() => ({ error:`声音识别失败（HTTP ${response.status}）` }));
    if (!response.ok) throw new Error(String(payload.error || "声音识别失败"));
    return payload as T;
  },
  assetAction<T>(body:unknown, signal?:AbortSignal) { return postJson<T>("/api/assistant/assets/action", body, { signal }, "素材操作失败"); },
};
