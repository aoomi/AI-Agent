<script setup lang="ts">
export type TaskTreeItem = {
  id:string;
  title:string;
  progress?:string;
  status?:"进行中" | "待审核" | "已完成" | "未开始" | "失败" | "已暂停" | "已失效";
  children?:TaskTreeItem[];
  open?:boolean;
};

defineProps<{ node:TaskTreeItem; level?:number }>();
</script>

<template>
  <details v-if="node.children?.length" class="task-tree-branch" :open="node.open">
    <summary class="task-tree-row" :style="{ '--task-level': level || 0 }">
      <span class="task-tree-chevron">⌄</span>
      <svg class="task-tree-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M3 7.5h7l2 2h9v9.5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7.5Z"/><path d="M3 7.5V5a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v2.5"/></svg>
      <strong>{{ node.title }}</strong>
      <span class="task-tree-progress">{{ node.progress }}</span>
      <span v-if="node.status" :class="['task-tree-status', `is-${node.status}`]">{{ node.status }}</span>
    </summary>
    <div class="task-tree-children">
      <TaskTreeNode v-for="child in node.children" :key="child.id" :node="child" :level="(level || 0) + 1" />
    </div>
  </details>
  <div v-else class="task-tree-row task-tree-leaf" :style="{ '--task-level': level || 0 }">
    <span class="task-tree-chevron"></span>
    <svg class="task-tree-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M6 3h9l4 4v14H6V3Z"/><path d="M15 3v5h4M9 13h7M9 17h5"/></svg>
    <strong>{{ node.title }}</strong>
    <span class="task-tree-progress">{{ node.progress }}</span>
    <span v-if="node.status" :class="['task-tree-status', `is-${node.status}`]">{{ node.status }}</span>
  </div>
</template>
