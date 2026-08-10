<script setup lang="ts">
defineProps<{ cardClass?: string | Record<string, boolean> }>();
defineEmits<{ close: [] }>();
</script>

<template>
  <div class="dialog-layer" @click.self="$emit('close')">
    <section class="dialog-card" :class="cardClass"><slot /></section>
  </div>
</template>
