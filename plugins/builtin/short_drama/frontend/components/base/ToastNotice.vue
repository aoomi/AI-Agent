<script setup lang="ts">
defineProps<{ message:string }>();
</script>

<template>
  <div class="toast">✓ {{message}}</div>
</template>
