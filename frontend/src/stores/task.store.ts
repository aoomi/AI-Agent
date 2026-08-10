import { reactive } from "vue";
import type { PlatformTask, TaskRequestContext, TaskService } from "../services/task-service";

export function createTaskStore(service: TaskService, context: TaskRequestContext) {
  const state = reactive({
    items: [] as PlatformTask[],
    selectedTask: null as PlatformTask | null,
    loading: false,
    error: "",
  });
  let timer = 0;

  async function refresh(projectId?: string): Promise<void> {
    state.loading = true; state.error = "";
    try {
      state.items = await service.list(context, projectId);
      if (state.selectedTask) state.selectedTask = state.items.find(item => item.task_id === state.selectedTask?.task_id) ?? null;
    } catch (error) {
      state.error = error instanceof Error ? error.message : "TASK_REQUEST_FAILED";
    } finally { state.loading = false; }
  }

  async function select(taskId: string): Promise<void> { state.selectedTask = await service.detail(context, taskId); }
  async function cancel(taskId: string): Promise<void> { state.selectedTask = await service.cancel(context, taskId); await refresh(state.selectedTask.project_id); }
  async function resume(taskId: string): Promise<void> { state.selectedTask = await service.resume(context, taskId); await refresh(state.selectedTask.project_id); }
  function startRealtime(projectId?: string, intervalMs = 1000): void {
    stopRealtime(); void refresh(projectId);
    timer = window.setInterval(() => void refresh(projectId), Math.max(250, intervalMs));
  }
  function stopRealtime(): void { if (timer) window.clearInterval(timer); timer = 0; }

  return { state, refresh, select, cancel, resume, startRealtime, stopRealtime };
}

export type TaskStore = ReturnType<typeof createTaskStore>;
