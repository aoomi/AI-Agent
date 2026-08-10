<script setup lang="ts">
defineProps<{ message: string; progress: string }>();
defineEmits<{ stop: [] }>();
</script>

<template>
  <div class="outline-page-progress" role="status" aria-live="polite">
    <div>{{ message }}<span v-if="progress">{{ progress }}</span></div>
    <button class="stop-generation" @click="$emit('stop')">停止生成</button>
  </div>
</template>
