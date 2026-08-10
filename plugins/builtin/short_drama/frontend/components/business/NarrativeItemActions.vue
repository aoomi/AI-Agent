<script setup lang="ts">
defineProps<{ disabled?:boolean; copied?:boolean; deleteLabel?:string }>();
defineEmits<{ delete:[]; copy:[]; quote:[] }>();
</script>

<template>
  <span class="message-actions episode-actions" contenteditable="false">
    <button :disabled="disabled" :aria-label="deleteLabel || '删除本集'" title="删除" @click="$emit('delete')"><svg aria-hidden="true"><use href="#icon-trash-simple" /></svg></button>
    <button :aria-label="copied ? '已复制' : '复制'" title="复制" @click="$emit('copy')"><svg aria-hidden="true"><use :href="copied ? '#icon-check-outline' : '#icon-copy-outline'" /></svg></button>
    <button aria-label="引用" title="引用" @click="$emit('quote')"><svg aria-hidden="true"><use href="#icon-quote-outline" /></svg></button>
  </span>
</template>
