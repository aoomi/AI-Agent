<script setup lang="ts">
defineProps<{
  label?:string;
  modelValue:string|number;
  min:string|number;
  max:string|number;
  step?:string|number;
  caption?:string;
  display:string;
}>();

defineEmits<{ "update:modelValue":[value:string] }>();
</script>

<template>
  <label>{{label}}<input type="range" :min="min" :max="max" :step="step" :value="modelValue" @input="$emit('update:modelValue',($event.target as HTMLInputElement).value)"><div v-if="caption" class="range-caption"><span>{{caption}}</span><b>{{display}}</b></div><span v-else>{{display}}</span></label>
</template>
