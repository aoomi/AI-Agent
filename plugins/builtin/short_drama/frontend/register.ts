import ShortDramaWorkspace from "./App.vue";
import { registerPluginSlot } from "../../../../frontend/src/plugin-slots/registry";

export function registerShortDramaFrontend(): void {
  registerPluginSlot({
    id: "short_drama.workspace",
    slot: "canvas",
    component: ShortDramaWorkspace,
    order: 100,
  });
}
