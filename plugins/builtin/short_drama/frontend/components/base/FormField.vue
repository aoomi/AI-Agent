<script setup lang="ts">
defineProps<{ label?:string }>();
</script>

<template>
  <label>{{label}}<slot /></label>
</template>
