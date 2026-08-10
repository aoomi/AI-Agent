<script setup lang="ts">
import { provide } from "vue";
import {
  appRuntimeKey,
  createAppRuntime,
} from "../../plugins/builtin/short_drama/frontend/app-runtime";
import { registerShortDramaFrontend } from "../../plugins/builtin/short_drama/frontend/register";
import { registerSystemAgentsFrontend } from "../../plugins/builtin/system_agents/frontend/register";
import CanvasSlot from "./plugin-slots/slots/CanvasSlot.vue";
import { listPluginSlots } from "./plugin-slots/registry";

provide(appRuntimeKey, createAppRuntime());
registerShortDramaFrontend();
registerSystemAgentsFrontend();
const canvasPlugins = listPluginSlots("canvas");
</script>

<template>
  <div class="platform-shell">
    <CanvasSlot>
      <component :is="registration.component" v-for="registration in canvasPlugins" :key="registration.id" />
    </CanvasSlot>
  </div>
</template>

<style scoped>
.platform-shell{position:relative;width:100%;height:100%;min-width:0;min-height:0;overflow:hidden}
.canvas-slot{position:absolute;inset:0;min-width:0;min-height:0;overflow:hidden}
</style>
