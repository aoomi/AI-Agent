<script setup lang="ts">
const props = withDefaults(defineProps<{
  title:string;
  current?:number;
  total?:number;
  elapsedSeconds?:number;
}>(), { current:0, total:0, elapsedSeconds:0 });

function formatElapsed(seconds:number) {
  const safeSeconds = Math.max(0, Math.floor(Number(seconds) || 0));
  const minutes = Math.floor(safeSeconds / 60);
  const remainingSeconds = String(safeSeconds % 60).padStart(2, "0");
  return minutes ? `${minutes}m ${remainingSeconds}s` : `${remainingSeconds}s`;
}
</script>

<template>
  <header class="workflow-status-header">
    <div class="workflow-status-summary">
      <h2>{{ props.title }}</h2>
      <strong>No:{{ props.current }}/{{ props.total }}</strong>
      <strong>Time:{{ formatElapsed(props.elapsedSeconds) }}</strong>
    </div>
    <div v-if="$slots.actions" class="workflow-status-actions"><slot name="actions" /></div>
  </header>
</template>
