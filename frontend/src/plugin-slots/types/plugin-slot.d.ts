export type PluginSlotName = "toolbar" | "sidebar" | "canvas" | "navigation" | "settings";

export interface PluginSlotRegistration {
  id: string;
  slot: PluginSlotName;
  component: unknown;
  order?: number;
}
