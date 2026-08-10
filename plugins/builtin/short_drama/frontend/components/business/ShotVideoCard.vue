<script setup lang="ts">
import BaseButton from "../base/BaseButton.vue";
import GenerationPlaceholder from "../base/GenerationPlaceholder.vue";

type ShotVideo = {
  episode:number; shotNumber:number; videoUrl:string; status:"pending"|"generating"|"completed"|"failed"; error:string;
  width:number; height:number; fps:number; model:string; lipSyncStatus?:string; lipSyncAuditStatus?:"pass"|"needs_fix";
  lipSyncOffsetMs?:number; lipSyncConfidence?:number; lipSyncError?:string;
};
defineProps<{ asset:ShotVideo; durationLabel:string; audioLabel:string; generationRunning:boolean; reviewRejected:boolean }>();
defineEmits<{ retry:[]; reject:[]; preview:[url:string] }>();
</script>

<template>
  <article :class="{issue:asset.status==='failed'||asset.lipSyncStatus==='failed'||reviewRejected}">
    <div class="shot-top"><b>第{{asset.episode}}集 · 镜头{{asset.shotNumber}}</b></div>
    <video v-if="asset.videoUrl" class="shot-video-preview clickable-preview-video" :src="asset.videoUrl" role="button" tabindex="0" title="点击放大预览" @click="$emit('preview',asset.videoUrl)" @keyup.enter="$emit('preview',asset.videoUrl)" />
    <GenerationPlaceholder v-else class="shot-image-placeholder" :failed="asset.status==='failed'" :message="asset.status==='generating'?'正在生成视频…':asset.status==='failed'?'本次生成失败':'等待生成'" :error="asset.error?asset.error:''" />
    <small>{{asset.width}}×{{asset.height}} · {{asset.fps}}fps · {{asset.model}}</small>
    <small class="generation-time">耗时 {{durationLabel}} · 配音 {{audioLabel}}<span v-if="asset.lipSyncAuditStatus"> · 口型 {{asset.lipSyncAuditStatus==='pass'?'通过':'需修复'}} · 偏移 {{asset.lipSyncOffsetMs||0}}ms · 置信度 {{(asset.lipSyncConfidence||0).toFixed(2)}}</span></small>
    <small v-if="asset.lipSyncError" class="generation-error">{{asset.lipSyncError}}</small>
    <div class="card-actions"><BaseButton :disabled="generationRunning" @click="$emit('retry')">单独重做</BaseButton><BaseButton class="review-reject" :disabled="asset.status!=='completed'||generationRunning" @click="$emit('reject')">驳回并重做</BaseButton></div>
  </article>
</template>
