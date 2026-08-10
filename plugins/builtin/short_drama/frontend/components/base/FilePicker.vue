<script setup lang="ts">
import BaseButton from "./BaseButton.vue";

withDefaults(defineProps<{ accept?:string; disabled?:boolean }>(), { accept:"", disabled:false });
const emit = defineEmits<{ select:[file:File] }>();

function chooseFile(accept:string) {
  const input = document.createElement("input");
  input.type = "file";
  input.accept = accept;
  input.onchange = () => {
    const file = input.files?.[0];
    if (file) emit("select", file);
  };
  input.click();
}
</script>

<template>
  <BaseButton :disabled="disabled" @click="chooseFile(accept)"><slot /></BaseButton>
</template>
