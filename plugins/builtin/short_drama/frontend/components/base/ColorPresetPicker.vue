<script setup lang="ts">
defineProps<{ modelValue: string; colors: string[] }>();
const emit = defineEmits<{ "update:modelValue": [value: string] }>();
</script>

<template>
  <div class="color-presets" role="group" aria-label="颜色预设">
    <button
      v-for="color in colors"
      :key="color"
      type="button"
      :style="{ background: color }"
      :aria-label="`选择颜色 ${color}`"
      :aria-pressed="modelValue.toUpperCase() === color.toUpperCase()"
      @click="emit('update:modelValue', color)"
    ></button>
  </div>
</template>
