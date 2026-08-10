<script setup lang="ts">
defineProps<{
  message: string;
  failed?: boolean;
  error?: string;
}>();
</script>

<template>
  <div :class="{ failed }"><b>{{ message }}</b><small v-if="error">{{ error }}</small></div>
</template>
