<script setup lang="ts">
import BaseButton from "../base/BaseButton.vue";
import FilePicker from "../base/FilePicker.vue";
import GenerationPlaceholder from "../base/GenerationPlaceholder.vue";

type CharacterAsset = { id:string; label:string; imageUrl:string; status:"pending"|"generating"|"completed"|"failed"; error:string };
const props = defineProps<{ asset:CharacterAsset; current:boolean; canGenerate:boolean; reviewLabel:string; durationLabel:string }>();
const emit = defineEmits<{ preview:[src:string]; generate:[]; stop:[]; replace:[file:File]; drop:[file?:File] }>();

function dropFile(event:DragEvent) {
  event.preventDefault();
  emit("drop", event.dataTransfer?.files?.[0]);
}
</script>

<template>
  <article class="character-asset-card" @dragover.prevent @drop="dropFile">
    <BaseButton v-if="current&&asset.imageUrl" class="character-asset-image" @click="$emit('preview',asset.imageUrl)"><img :src="asset.imageUrl" draggable="false"></BaseButton>
    <GenerationPlaceholder v-else class="character-asset-placeholder" :failed="current&&asset.status==='failed'" :message="current&&asset.status==='generating'?'正在生成…':current&&asset.status==='failed'?'生成失败':!canGenerate?'等待正面基准图审核':'拖入图片或等待生成'" :error="current&&asset.error?asset.error:''" />
    <div class="character-asset-meta"><strong>{{asset.label}}</strong><small>{{reviewLabel}} · {{current&&asset.status==='generating'?'生成中':current?`耗时 ${durationLabel}`:'耗时 未记录'}}</small></div>
    <div class="character-asset-actions">
      <BaseButton :disabled="!canGenerate" :class="{danger:asset.status==='generating'}" @click="asset.status==='generating'?$emit('stop'):$emit('generate')">{{asset.status==='generating'?'停止生成':current&&asset.imageUrl?'重新生成':'生成图片'}}</BaseButton>
      <FilePicker accept="image/*" :disabled="asset.status==='generating'||!canGenerate" @select="$emit('replace',$event)">替换图片</FilePicker>
    </div>
  </article>
</template>
