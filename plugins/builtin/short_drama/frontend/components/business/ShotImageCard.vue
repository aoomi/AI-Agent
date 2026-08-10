<script setup lang="ts">
import BaseButton from "../base/BaseButton.vue";
import FilePicker from "../base/FilePicker.vue";
import GenerationPlaceholder from "../base/GenerationPlaceholder.vue";

type ShotImage = { episode:number; shotNumber:number; prompt:string; imageUrl:string; width:number; height:number; status:"pending"|"generating"|"completed"|"failed"; error:string };
defineProps<{ asset:ShotImage; durationLabel:string; generationRunning:boolean }>();
defineEmits<{ preview:[src:string]; repair:[]; retry:[]; replace:[file:File]; updatePrompt:[value:string]; save:[] }>();
</script>

<template>
  <article :class="{issue:asset.status==='failed'}">
    <div class="shot-top"><b>第{{asset.episode}}集 · 镜头{{asset.shotNumber}}</b><small v-if="durationLabel!=='未记录'" class="shot-title-duration">耗时 {{durationLabel}}</small></div>
    <BaseButton v-if="asset.imageUrl" class="media" :class="{landscape:asset.width>asset.height}" @click="$emit('preview',asset.imageUrl)"><img :src="asset.imageUrl"></BaseButton>
    <GenerationPlaceholder v-else class="shot-image-placeholder" :failed="asset.status==='failed'" :message="asset.status==='generating'?'正在生成镜头画面…':asset.status==='failed'?'本次生成失败':'等待生成'" :error="asset.error?asset.error:''" />
    <label class="shot-prompt-editor"><textarea :value="asset.prompt" aria-label="分镜提示词" @input="$emit('updatePrompt',($event.target as HTMLTextAreaElement).value)" @change="$emit('save')" /></label>
    <div class="card-actions">
      <BaseButton v-if="asset.imageUrl" @click="$emit('preview',asset.imageUrl)">放大</BaseButton>
      <BaseButton v-if="asset.imageUrl" :disabled="generationRunning" @click="$emit('repair')">局部修复</BaseButton>
      <BaseButton :disabled="generationRunning" @click="$emit('retry')">重新生成</BaseButton>
      <FilePicker accept="image/*" :disabled="asset.status==='generating'" @select="$emit('replace',$event)">替换图片</FilePicker>
    </div>
  </article>
</template>
