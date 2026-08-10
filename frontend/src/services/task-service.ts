export type TaskStatus = "queued" | "running" | "waiting_human" | "paused" | "completed" | "failed" | "cancelled";

export interface PlatformTask {
  task_id: string;
  tenant_id: string;
  project_id: string;
  operation_key: string;
  task_type: string;
  status: TaskStatus;
  payload: Record<string, unknown>;
}

export interface TaskRequestContext {
  requestId: string;
  traceId: string;
  identityId: string;
  identityKind: "user" | "service" | "agent";
  tenantId: string;
}

export class TaskService {
  constructor(private readonly baseUrl = "") {}

  async list(context: TaskRequestContext, projectId?: string): Promise<PlatformTask[]> {
    const query = projectId ? `?project_id=${encodeURIComponent(projectId)}` : "";
    const response = await this.request<{ items: PlatformTask[] }>(context, `/api/v1/tasks${query}`);
    return response.items;
  }

  detail(context: TaskRequestContext, taskId: string): Promise<PlatformTask> {
    return this.request(context, `/api/v1/tasks/${encodeURIComponent(taskId)}`);
  }

  cancel(context: TaskRequestContext, taskId: string): Promise<PlatformTask> {
    return this.request(context, `/api/v1/tasks/${encodeURIComponent(taskId)}/cancel`, "POST");
  }

  resume(context: TaskRequestContext, taskId: string): Promise<PlatformTask> {
    return this.request(context, `/api/v1/tasks/${encodeURIComponent(taskId)}/resume`, "POST");
  }

  private async request<T>(context: TaskRequestContext, path: string, method = "GET"): Promise<T> {
    const response = await fetch(this.baseUrl + path, {
      method,
      headers: {
        "X-Request-Id": context.requestId,
        "X-Trace-Id": context.traceId,
        "X-Identity-Id": context.identityId,
        "X-Identity-Kind": context.identityKind,
        "X-Tenant-Id": context.tenantId,
      },
    });
    if (!response.ok) throw new Error(`TASK_REQUEST_FAILED:${response.status}`);
    const envelope = await response.json() as { data: T };
    return envelope.data;
  }
}
