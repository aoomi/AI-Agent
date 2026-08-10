import SystemAgentPanel from "./SystemAgentPanel.vue";
import ProviderPanel from "./ProviderPanel.vue";
import PluginManagementPanel from "./PluginManagementPanel.vue";
import IndustryAgentPanel from "./IndustryAgentPanel.vue";
import { registerPluginSlot } from "../../../../frontend/src/plugin-slots/registry";

export function registerSystemAgentsFrontend(): void {
  registerPluginSlot({ id: "system_agents.configuration", slot: "settings", component: SystemAgentPanel, order: 10 });
  registerPluginSlot({ id: "system_agents.providers", slot: "settings", component: ProviderPanel, order: 20 });
  registerPluginSlot({ id: "system_agents.plugins", slot: "settings", component: PluginManagementPanel, order: 30 });
  registerPluginSlot({ id: "system_agents.industry", slot: "settings", component: IndustryAgentPanel, order: 40 });
}
