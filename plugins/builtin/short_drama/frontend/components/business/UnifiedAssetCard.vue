<script setup lang="ts">
import MediaOverlayControls from "../base/MediaOverlayControls.vue";
import StatusPulse from "../base/StatusPulse.vue";

export type UnifiedAssetSlide = { key:string; label:string; imageUrl?:string; previewId?:string; status:string; generating:boolean; showAccept:boolean; variant?:unknown; readOnly?:boolean };
export type UnifiedAssetItem = {
  name:string; image_prompt:string; image_url?:string; status?:string; error?:string; model3d_status?:string; model3d_error?:string;
  model3d_result?:{ model_url:string; blend_url:string; source_video_url?:string; vertex_count?:number; face_count?:number; renders?:Array<{label:string;url:string}> };
};

defineProps<{ kind:"character"|"prop"|"scene"; item:UnifiedAssetItem; slides:UnifiedAssetSlide[]; introOpen:string; canAcceptBaseline:boolean; userError:string }>();
defineEmits<{
  pointerDown:[event:PointerEvent]; pointerMove:[event:PointerEvent]; pointerUp:[event:PointerEvent]; pointerCancel:[event:PointerEvent];
  toggleIntro:[slide:UnifiedAssetSlide]; import:[slide:UnifiedAssetSlide]; regenerate:[slide:UnifiedAssetSlide]; repair:[slide:UnifiedAssetSlide];
  closeIntro:[]; preview:[slide:UnifiedAssetSlide]; reference:[slide:UnifiedAssetSlide]; accept:[slide:UnifiedAssetSlide]; confirmBaseline:[]; generate3d:[]; confirm3d:[]; stop3d:[]; upscale:[];
}>();

function stateLabel(item:UnifiedAssetItem) {
  if (item.model3d_status === "generating") return "Klein‑9B、TripoSR与Blender后台处理中";
  if (item.model3d_status === "waiting_confirmation") return "3D结构待人工确认；不审核面部相似度";
  if (item.model3d_status === "confirmed") return "3D资产已完成";
  if (item.status === "confirmed") return "固定角度图已完成";
  if (item.status === "generating") return "正在引用定位基准图生成";
  if (item.status === "failed") return "生成失败";
  return item.image_url ? "定位基准图待确认" : "待生成定位基准图";
}
</script>

<template>
  <article class="asset-profile-card">
    <div class="asset-profile-media">
      <div class="asset-photo-carousel" @pointerdown="$emit('pointerDown',$event)" @pointermove="$emit('pointerMove',$event)" @pointerup="$emit('pointerUp',$event)" @pointercancel="$emit('pointerCancel',$event)">
        <div v-for="slide in slides" :key="slide.key" class="asset-photo-slide">
          <span class="asset-photo-label">{{slide.label}}</span>
          <img v-if="slide.imageUrl" :src="slide.imageUrl" :alt="`${item.name}${slide.label}`" :data-preview-id="slide.previewId" class="clickable-preview-image" role="button" tabindex="0" draggable="false" @click="$emit('preview',slide)" @keyup.enter="$emit('preview',slide)" />
          <div v-else class="asset-profile-media-placeholder"><StatusPulse v-if="slide.generating" text="此图正在生成中……" /><span v-else>等待生图</span></div>
          <div v-if="slide.imageUrl&&slide.generating" class="asset-image-generation-overlay"><StatusPulse text="此图正在生成中……" /></div>
          <MediaOverlayControls v-if="!slide.readOnly" media-type="image" :generating="slide.generating" :can-reference="Boolean(slide.imageUrl)" :show-repair="Boolean(slide.imageUrl)" :show-accept="slide.showAccept" accept-label="就要这张" @intro="$emit('toggleIntro',slide)" @import="$emit('import',slide)" @regenerate="$emit('regenerate',slide)" @repair="$emit('repair',slide)" @reference="$emit('reference',slide)" @confirm-selection="$emit('accept',slide)" />
        </div>
      </div>
      <div v-if="introOpen.startsWith(`${kind}:${item.name}:`)" class="asset-intro-panel" @click.stop>
        <button class="asset-intro-close" type="button" aria-label="关闭简介" title="关闭" @click="$emit('closeIntro')">×</button>
        <strong>{{item.name}}</strong><p>{{item.image_prompt}}</p><p v-if="item.error" class="outline-error">{{userError}}</p>
        <button v-if="canAcceptBaseline" @click="$emit('confirmBaseline')">{{kind==='character'?'确认基准图并生成其余人物角度':'确认45°基准图并自动生成3D七角度'}}</button>
        <button v-if="item.image_url&&item.model3d_status!=='generating'" type="button" @click="$emit('generate3d')">{{item.model3d_result?'重新生成3D资产':'生成3D资产'}}</button>
        <button v-if="item.model3d_status==='waiting_confirmation'" type="button" @click="$emit('confirm3d')">确认3D结构</button>
        <button v-if="item.model3d_status==='generating'" type="button" @click="$emit('stop3d')">停止3D生成</button>
        <p v-if="item.model3d_error" class="outline-error">{{item.model3d_error}}</p>
        <p v-if="item.model3d_result" class="asset-3d-result"><a :href="item.model3d_result.model_url" download>下载GLB</a><a :href="item.model3d_result.blend_url" download>下载Blend</a><a v-if="item.model3d_result.source_video_url" :href="item.model3d_result.source_video_url" download>下载H3源视频</a><span>{{item.model3d_result.vertex_count||0}}顶点 / {{item.model3d_result.face_count||0}}面</span></p>
        <div v-if="item.model3d_result?.renders?.length" class="asset-3d-renders"><a v-for="render in item.model3d_result.renders" :key="render.label" :href="render.url" target="_blank"><img :src="render.url" :alt="`${item.name}${render.label}3D审核图`" /><small>{{render.label}}</small></a></div>
        <small>{{stateLabel(item)}}</small>
      </div>
      <button v-if="item.image_url" class="asset-upscale-button" type="button" @click="$emit('upscale')">AI图片超分</button>
    </div>
  </article>
</template>
