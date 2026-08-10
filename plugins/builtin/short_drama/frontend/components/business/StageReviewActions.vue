<script setup lang="ts">
import BaseButton from "../base/BaseButton.vue";

defineProps<{
  hasManualEdits:boolean;
  showSubmit:boolean;
  showAudit:boolean;
  auditRunning:boolean;
  showConfirm:boolean;
  showStop:boolean;
  showRollback:boolean;
}>();
defineEmits<{ submit:[]; audit:[]; confirm:[]; stop:[]; rollback:[]; clear:[] }>();
</script>

<template>
  <div class="canvas-head-actions">
    <span v-if="hasManualEdits" class="autosave">● 已自动保存</span>
    <BaseButton v-if="showSubmit" class="primary" @click="$emit('submit')">提交修改</BaseButton>
    <BaseButton v-if="showAudit" :class="{danger:auditRunning}" @click="$emit('audit')">{{auditRunning?'停止审核':'审核'}}</BaseButton>
    <BaseButton v-if="showConfirm" class="primary" @click="$emit('confirm')">确认并进入下一步</BaseButton>
    <BaseButton v-if="showStop" class="header-stop-generation" @click="$emit('stop')">停止生成</BaseButton>
    <BaseButton v-if="showRollback" class="header-rollback-data" @click="$emit('rollback')">回滚数据</BaseButton>
    <BaseButton class="header-clear-all" @click="$emit('clear')">清空数据</BaseButton>
  </div>
</template>
