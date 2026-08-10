<script setup lang="ts">
defineProps<{ modelValue:number; episodeCount:number }>();
const emit = defineEmits<{ "update:modelValue":[value:number] }>();
</script>

<template>
  <label class="workflow-episode-selector">
    <select :value="modelValue" aria-label="选择显示集数" @change="emit('update:modelValue', Number(($event.target as HTMLSelectElement).value))">
      <option :value="0">全剧集</option>
      <option v-for="episode in episodeCount" :key="episode" :value="episode">第{{ episode }}集</option>
    </select>
  </label>
</template>
