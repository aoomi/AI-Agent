<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted } from "vue";
import type { TaskStore } from "../../stores/task.store";

const props = defineProps<{ store: TaskStore }>();
const selected = computed(() => props.store.state.selectedTask);
const progress = (task: { payload: Record<string, unknown>; status: string }) =>
  task.status === "completed" ? 100 : Number(task.payload.progress_percent ?? 0);

onMounted(() => props.store.startRealtime());
onBeforeUnmount(() => props.store.stopRealtime());
</script>

<template>
  <section class="task-center" aria-label="任务中心">
    <header><strong>任务中心</strong><span v-if="store.state.loading">更新中</span></header>
    <p v-if="store.state.error" class="error">{{ store.state.error }}</p>
    <div class="task-list">
      <button v-for="task in store.state.items" :key="task.task_id" type="button" @click="store.select(task.task_id)">
        <span>{{ task.task_type }}</span><span>{{ task.status }} · {{ progress(task) }}%</span>
      </button>
      <span v-if="!store.state.loading && !store.state.items.length">暂无任务</span>
    </div>
    <aside v-if="selected" class="task-detail">
      <span>{{ selected.task_id }}</span><span>{{ selected.project_id }}</span><span>{{ selected.status }}</span>
      <button v-if="!['completed', 'cancelled'].includes(selected.status)" type="button" @click="store.cancel(selected.task_id)">取消</button>
      <button v-if="['paused', 'failed'].includes(selected.status)" type="button" @click="store.resume(selected.task_id)">恢复</button>
    </aside>
  </section>
</template>

<style scoped>
.task-center{display:flex;gap:12px;align-items:center;padding:8px 12px;background:#15171c;color:#eef1f7;font-size:12px}.task-center header,.task-detail{display:flex;gap:8px;align-items:center}.task-list{display:flex;gap:6px;overflow:auto;flex:1}.task-list button,.task-detail button{border:1px solid #39404d;background:#232833;color:inherit;border-radius:6px;padding:5px 8px}.task-list button{display:flex;gap:10px}.error{color:#ff8f8f;margin:0}
</style>
