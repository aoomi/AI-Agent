<script setup lang="ts">
withDefaults(defineProps<{ text?: string }>(), { text: "Thinking..." });
</script>

<template>
  <span class="status-pulse" role="status" aria-live="polite">{{ text }}</span>
</template>
