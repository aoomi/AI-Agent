<script setup lang="ts">
import BaseButton from "./BaseButton.vue";
import DialogCloseButton from "./DialogCloseButton.vue";

defineProps<{ type:"image"|"video"; src:string; hasMultiple?:boolean; onClose:()=>void }>();
const emit = defineEmits<{ previous:[]; next:[]; replace:[] }>();
</script>

<template>
  <div class="modal" @click="onClose" @dragstart.prevent>
    <DialogCloseButton @close="onClose" />
    <template v-if="type==='image'">
      <div class="preview-viewer">
        <BaseButton v-if="hasMultiple" class="preview-arrow previous" aria-label="上一张" @click.stop="$emit('previous')"><svg aria-hidden="true"><use href="#icon-chevron-left" /></svg></BaseButton>
        <div class="preview-stage" @click.stop>
          <img :src="src" draggable="false">
          <div class="preview-actions preview-single-action"><BaseButton @click="$emit('replace')">替换图片</BaseButton></div>
        </div>
        <BaseButton v-if="hasMultiple" class="preview-arrow next" aria-label="下一张" @click.stop="$emit('next')"><svg aria-hidden="true"><use href="#icon-chevron-right" /></svg></BaseButton>
      </div>
    </template>
    <video v-else :src="src" controls autoplay @click.stop />
  </div>
</template>
