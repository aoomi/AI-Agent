<script setup lang="ts">
defineProps<{
  running?:boolean;
  primaryLabel?:string;
  primaryDisabled?:boolean;
  nextLabel?:string;
  nextDisabled?:boolean;
  showImport?:boolean;
}>();
defineEmits<{ import:[]; primary:[]; pause:[]; next:[] }>();
</script>

<template>
  <div class="workflow-action-bar">
    <button v-if="showImport !== false" class="workflow-action-import" @click="$emit('import')">导入</button>
    <button v-if="!running && primaryLabel" class="workflow-action-primary" :disabled="primaryDisabled" @click="$emit('primary')">{{ primaryLabel }}</button>
    <button v-if="running" class="workflow-action-pause" @click="$emit('pause')">暂停</button>
    <button v-if="nextLabel" class="workflow-action-next" :disabled="nextDisabled" @click="$emit('next')">{{ nextLabel }}</button>
    <slot name="status" />
    <slot />
  </div>
</template>

<style scoped>
.workflow-action-bar{display:flex;align-items:center;gap:10px;flex-wrap:wrap;width:100%;padding:16px 18px;border:1px solid #e2e6ec;border-radius:18px;background:#fff;box-sizing:border-box}
.workflow-action-bar button{min-height:44px;padding:0 22px;border:1px solid #d6dce5;border-radius:14px;background:#fff;color:#20242a;font:inherit;white-space:nowrap}
.workflow-action-bar button:disabled{opacity:.42;cursor:not-allowed}
.workflow-action-primary,.workflow-action-next{border-color:#8ab5f5!important;background:#edf5ff!important;color:#2468be!important}
.workflow-action-pause{border-color:#e4b3ad!important;background:#fff5f3!important;color:#b24336!important}
.workflow-action-bar :deep(.script-stage-indicator){margin-left:auto}
</style>
