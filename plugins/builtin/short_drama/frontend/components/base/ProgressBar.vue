<script setup lang="ts">
defineProps<{ width: string }>();
</script>

<template>
  <div class="progress"><i :style="{ width }" /></div>
</template>
