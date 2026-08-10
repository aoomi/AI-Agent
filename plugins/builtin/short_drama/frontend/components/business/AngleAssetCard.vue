<script setup lang="ts">
import BaseButton from "../base/BaseButton.vue";
import GenerationPlaceholder from "../base/GenerationPlaceholder.vue";

type AngleAsset = { id:string; label:string; prompt:string; imageUrl:string; status:"pending"|"generating"|"completed"|"failed"; error:string };
defineProps<{ asset:AngleAsset; promptLabel:string; durationLabel:string }>();
defineEmits<{ preview:[src:string]; generate:[asset:AngleAsset] }>();
</script>

<template>
  <article class="character-asset-card">
    <BaseButton v-if="asset.imageUrl" class="character-asset-image" @click="$emit('preview',asset.imageUrl)"><img :src="asset.imageUrl" draggable="false"></BaseButton>
    <GenerationPlaceholder v-else class="character-asset-placeholder" :failed="asset.status==='failed'" :message="asset.status==='generating'?'正在生成…':asset.status==='failed'?'生成失败':'等待生成'" :error="asset.error?asset.error:''" />
    <div class="character-asset-meta"><strong>{{asset.label}}</strong><small>{{asset.status==='completed'?`耗时 ${durationLabel}`:'待生成'}}</small></div>
    <details class="shot-prompt-log"><summary>查看{{promptLabel}}提示词</summary><pre>{{asset.prompt}}</pre></details>
    <BaseButton :disabled="asset.status==='generating'" @click="$emit('generate',asset)">{{asset.imageUrl?'重新生成':'生成图片'}}</BaseButton>
  </article>
</template>
