<script setup lang="ts">
defineProps<{ title:string; copied?:boolean; copyLabel:string }>();
defineEmits<{ copy:[]; quote:[] }>();
</script>

<template>
  <div class="narrative-title-row">
    <slot name="title"><h3 class="outline-drama-title">{{ title }}</h3></slot>
    <span class="narrative-title-actions">
      <button :aria-label="copied ? '已复制全部剧集' : copyLabel" :title="copyLabel" @click="$emit('copy')"><svg aria-hidden="true"><use :href="copied ? '#icon-check-outline' : '#icon-copy-outline'" /></svg></button>
      <button aria-label="引用全部剧集" title="引用全部剧集" @click="$emit('quote')"><svg aria-hidden="true"><use href="#icon-quote-outline" /></svg></button>
    </span>
  </div>
</template>
