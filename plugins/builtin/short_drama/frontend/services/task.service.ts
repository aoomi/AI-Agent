import { postJson, requestJsonOk } from "./api-client";

export type PlatformTaskStatus = "queued" | "running" | "completed" | "paused" | "cancelled" | "failed";
export type PlatformTask = {
  id:number; operation_key:string; request_id:string; label:string; status:PlatformTaskStatus; project_id:string; stage:string;
  episode:number | null; scope_id:string; position:number | null; queued_at:string; started_at:string | null; finished_at:string | null;
  error:{ name:string; code:string; message:string } | null; has_result:boolean;
};
export type RuntimeTask = {
  job_id:string; task_class:"text"|"image"|"video"; stage:string; status:string; project_id:string;
  pid:number|null; process_group:number|null; heartbeat_at:string; started_at:string; finished_at:string;
};
type TaskIdentity = { tenant_id:string; user_id:string; project_id:string };

export const taskService = {
  list(identity:TaskIdentity) {
    return requestJsonOk<{ tasks:PlatformTask[]; fault:{ code:string; message:string } | null }>(`/api/tasks?${new URLSearchParams(identity)}`, { cache:"no-store" }, "任务列表加载失败");
  },
  runtime(identity:TaskIdentity) {
    const query = new URLSearchParams({ ...identity, nonterminal_only:"true" });
    return requestJsonOk<{ tasks:RuntimeTask[] }>(`/api/tasks/runtime?${query}`, { cache:"no-store" }, "运行任务加载失败");
  },
  stop(payload:TaskIdentity & { operation_key:string }) { return postJson<{ stopped:boolean; status:string }>("/api/tasks/stop", payload, {}, "任务停止失败"); },
  resume(payload:TaskIdentity & { operation_key:string }) { return postJson<{ resumed:boolean; operation_key:string }>("/api/tasks/resume", payload, {}, "任务恢复失败"); },
  result<T>(payload:TaskIdentity & { operation_key:string }) {
    return requestJsonOk<{ task:PlatformTask; result:T | null }>(`/api/tasks/result?${new URLSearchParams(payload)}`, { cache:"no-store" }, "任务结果领取失败");
  },
};
