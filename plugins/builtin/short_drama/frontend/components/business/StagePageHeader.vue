<script setup lang="ts">
withDefaults(defineProps<{ title:string; subtitle?:string }>(), { subtitle:"" });
</script>

<template>
  <div class="canvas-head">
    <div><h1>{{title}}</h1><slot name="summary"><p v-if="subtitle">{{subtitle}}</p></slot></div>
    <slot name="activity" />
    <slot name="actions" />
  </div>
</template>
