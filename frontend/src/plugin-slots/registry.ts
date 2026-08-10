import type { PluginSlotRegistration, PluginSlotName } from "./types/plugin-slot";

const registrations = new Map<string, PluginSlotRegistration>();

export function registerPluginSlot(registration: PluginSlotRegistration): void {
  registrations.set(registration.id, registration);
}

export function unregisterPluginSlot(id: string): void {
  registrations.delete(id);
}

export function listPluginSlots(slot: PluginSlotName): PluginSlotRegistration[] {
  return [...registrations.values()].filter(item => item.slot === slot).sort((a, b) => (a.order ?? 0) - (b.order ?? 0));
}
