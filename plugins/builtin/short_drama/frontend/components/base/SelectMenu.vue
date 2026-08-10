<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from "vue";
import BaseButton from "./BaseButton.vue";

defineProps<{ modelValue:string; options:string[] }>();
const emit = defineEmits<{ "update:modelValue":[value:string] }>();
const root = ref<HTMLElement | null>(null);
const open = ref(false);

function choose(value:string) {
  emit("update:modelValue", value);
  open.value = false;
}
function closeOutside(event:PointerEvent) {
  if (!root.value?.contains(event.target as Node)) open.value = false;
}
onMounted(() => document.addEventListener("pointerdown", closeOutside));
onBeforeUnmount(() => document.removeEventListener("pointerdown", closeOutside));
</script>

<template>
  <div ref="root" class="ui-select">
    <BaseButton type="button" :class="{open}" @click="open=!open"><span>{{modelValue}}</span><i>⌄</i></BaseButton>
    <Transition name="picker">
      <div v-if="open" class="ui-select-menu">
        <BaseButton v-for="item in options" :key="item" type="button" :class="{active:item===modelValue}" @click="choose(item)"><span>{{item}}</span><i v-if="item===modelValue">✓</i></BaseButton>
      </div>
    </Transition>
  </div>
</template>
