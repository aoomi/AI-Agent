<script setup lang="ts">
defineProps<{
  mediaType: "image" | "video";
  generating?: boolean;
  showPlay?: boolean;
  canReference?: boolean;
  showRepair?: boolean;
  showAccept?: boolean;
  acceptLabel?: string;
}>();

defineEmits<{
  intro: [event: MouseEvent];
  import: [event: MouseEvent];
  regenerate: [event: MouseEvent];
  play: [event: MouseEvent];
  reference: [event: MouseEvent];
  repair: [event: MouseEvent];
  confirmSelection: [event: MouseEvent];
}>();
</script>

<template>
  <div class="media-overlay-controls" aria-label="媒体操作">
    <button class="media-control-button media-control-intro" type="button" :aria-label="mediaType === 'video' ? '视频简介' : '图片简介'" @click.stop="$emit('intro', $event)">
      <svg aria-hidden="true"><use href="#icon-grid-outline" /></svg>
    </button>
    <button v-if="showPlay" class="media-control-button media-control-play" type="button" aria-label="播放视频" @click.stop="$emit('play', $event)"><span aria-hidden="true"></span></button>
    <button v-if="canReference" class="media-control-button media-control-reference" type="button" aria-label="引用" @click.stop="$emit('reference', $event)"><svg aria-hidden="true"><use href="#icon-quote-outline" /></svg></button>
    <button v-if="showRepair" class="media-control-button" type="button" aria-label="局部修复" :disabled="generating" @click.stop="$emit('repair', $event)">修</button>
    <button v-if="showAccept" class="media-control-accept" type="button" @pointerdown.stop.prevent @click.stop.prevent="$emit('confirmSelection', $event)">{{ acceptLabel || '确认' }}</button>
    <div class="media-control-actions">
      <button class="media-control-button" type="button" :aria-label="mediaType === 'video' ? '导入视频' : '导入图片'" :disabled="generating" @click.stop="$emit('import', $event)">
        <svg aria-hidden="true"><use href="#icon-material-outline" /></svg>
      </button>
      <button class="media-control-button" type="button" :aria-label="generating ? '停止生成' : '重新生成'" @click.stop="$emit('regenerate', $event)">
        <span v-if="generating" class="media-control-stop" aria-hidden="true"></span>
        <svg v-else aria-hidden="true"><use href="#icon-cycle-outline" /></svg>
      </button>
    </div>
  </div>
</template>
