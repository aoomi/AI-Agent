<script setup lang="ts">
import BaseButton from "./BaseButton.vue";

defineProps<{
  label:string;
  modelValue:string;
  placeholder:string;
  swatches:string[];
}>();

defineEmits<{ "update:modelValue":[value:string] }>();
</script>

<template>
  <label>{{label}}<div class="color-input-row"><input type="color" :value="modelValue" @input="$emit('update:modelValue',($event.target as HTMLInputElement).value)"><input class="color-code" maxlength="7" :placeholder="placeholder" :value="modelValue" @input="$emit('update:modelValue',($event.target as HTMLInputElement).value)"><slot /></div><div class="color-swatches"><BaseButton v-for="color in swatches" :key="color" :class="{active:modelValue===color}" :style="{background:color}" @click="$emit('update:modelValue',color)"/></div></label>
</template>
