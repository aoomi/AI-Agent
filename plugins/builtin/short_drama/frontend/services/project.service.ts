import { postJson, requestJsonOk } from "./api-client";

export type ProjectPayload = {
  id?:string; tenant_id:string; user_id:string; name:string; category:string; topic:string; style:string;
  episode_count:number; duration_min:number; duration_max:number; upscale:string; language:string; subtitle:string; ai_label:string;
  lora_mode:"automatic"|"fixed"|"manual"|"exploration";lora_id:string;lora_exploration_seed:number|null;
};

export type StoredProject = ProjectPayload & { id:string; pinned:boolean; archived:boolean; archived_at:string | null; created_at:string; updated_at:string };
export type ProjectVersion = { version_id:string; stage:string; reason:string; created_at:string; media_count:number };

export const projectService = {
  list(identity:{ tenant_id:string; user_id:string }, includeArchived = false) {
    const query = new URLSearchParams({ ...identity, include_archived:String(includeArchived) });
    return requestJsonOk<{ projects:StoredProject[] }>(`/api/projects?${query}`, { cache:"no-store" }, "项目列表加载失败");
  },
  create(payload:ProjectPayload) { return postJson<{ project:StoredProject }>("/api/projects/create", payload, {}, "项目创建失败"); },
  update(payload:ProjectPayload & { id:string }) { return postJson<{ project:StoredProject }>("/api/projects/update", payload, {}, "项目保存失败"); },
  pin(payload:{ id:string; tenant_id:string; user_id:string }) { return postJson<{ project:StoredProject }>("/api/projects/pin", payload, {}, "项目置顶失败"); },
  remove(payload:{ id:string; tenant_id:string; user_id:string }) { return postJson<{ project:StoredProject }>("/api/projects/delete", payload, {}, "项目删除失败"); },
  archiveProject(payload:{ id:string; tenant_id:string; user_id:string }) { return postJson<{ project:StoredProject; version:ProjectVersion }>("/api/projects/archive", payload, {}, "项目归档失败"); },
  restoreProject(payload:{ id:string; tenant_id:string; user_id:string }) { return postJson<{ project:StoredProject }>("/api/projects/restore", payload, {}, "项目恢复失败"); },
  readStage<T>(payload:{ id:string; tenant_id:string; user_id:string; stage:string }) {
    return requestJsonOk<{ stage:{ data:T; updated_at:string; revision:number } | null }>(`/api/projects/stage?${new URLSearchParams(payload)}`, { cache:"no-store" }, "流程数据加载失败");
  },
  watchStage<T>(payload:{ id:string; tenant_id:string; user_id:string; stage:string; after_revision:number; timeout_seconds?:number; request_id:string }, signal?:AbortSignal) {
    const query = new URLSearchParams(Object.entries(payload).map(([key, value]) => [key, String(value)]));
    return requestJsonOk<{ changed:boolean; stage:{ data:T; updated_at:string; revision:number } | null }>(`/api/projects/stage/watch?${query}`, { cache:"no-store", signal }, "流程进度订阅失败");
  },
  cancelStageWatch(payload:{ id:string; tenant_id:string; user_id:string; stage:string; request_id:string }) {
    return postJson<{ cancelled:boolean }>("/api/projects/stage/watch/cancel", payload, {}, "停止流程进度订阅失败");
  },
  writeStage<T>(payload:{ id:string; tenant_id:string; user_id:string; stage:string; data:T }) {
    return postJson<{ stage:{ data:T; updated_at:string } }>("/api/projects/stage", payload, {}, "流程数据保存失败");
  },
  createVersion<T>(payload:unknown) {
    return postJson<T>("/api/projects/version", payload, {}, "项目版本创建失败");
  },
  versions(payload:{ project_id:string; tenant_id:string; user_id:string }) {
    return requestJsonOk<{ versions:ProjectVersion[] }>(`/api/projects/version?${new URLSearchParams(payload)}`, { cache:"no-store" }, "项目版本加载失败");
  },
  version<T>(payload:{ project_id:string; version_id:string; tenant_id:string; user_id:string }) {
    return requestJsonOk<T>(`/api/projects/version?${new URLSearchParams(payload)}`, { cache:"no-store" }, "项目版本读取失败");
  },
  rollback(payload:{ project_id:string; version_id:string; tenant_id:string; user_id:string }) {
    return postJson<{ project:StoredProject; version_id:string }>("/api/projects/version/rollback", payload, {}, "项目回滚失败");
  },
  exportUrl(payload:{ id:string; tenant_id:string; user_id:string }) {
    return `/api/projects/export?${new URLSearchParams(payload)}`;
  },
};
