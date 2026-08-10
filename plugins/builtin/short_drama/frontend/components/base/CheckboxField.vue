<script setup lang="ts">
withDefaults(defineProps<{ modelValue?:boolean; checked?:boolean }>(), { modelValue:undefined, checked:false });
defineEmits<{ "update:modelValue":[value:boolean] }>();
</script>

<template>
  <label><input type="checkbox" :checked="modelValue===undefined?checked:modelValue" @change="$emit('update:modelValue',($event.target as HTMLInputElement).checked)"><slot /></label>
</template>
