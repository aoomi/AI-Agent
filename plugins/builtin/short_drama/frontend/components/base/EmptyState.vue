<script setup lang="ts">
defineProps<{ title: string; message: string }>();
</script>

<template>
  <section class="empty-stage-card">
    <h2>{{ title }}</h2>
    <p>{{ message }}</p>
    <slot />
  </section>
</template>
