<script setup lang="ts">
defineEmits<{ close:[] }>();
</script>

<template>
  <button class="dialog-close-hit" type="button" aria-label="关闭" @click="$emit('close')">
    <span class="dialog-close-mask" aria-hidden="true">
      <svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6 6 18" /></svg>
    </span>
  </button>
</template>
