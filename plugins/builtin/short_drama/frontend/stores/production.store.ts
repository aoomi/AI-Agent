import { reactive } from "vue";
import type { AggregatedProductionStatus, ProductionScopeRecord, ProductionStatus } from "../types/production.ts";
import { aggregateProductionProgress, aggregateProductionStatus, mergeProductionScopeRecords, productionScopeKey } from "../utils/production-state.ts";

const allowedTransitions:Record<ProductionStatus, readonly ProductionStatus[]> = {
  idle:["queued", "running", "cancelled", "skipped", "stale"],
  queued:["running", "paused", "cancelled", "failed", "stale"],
  running:["auditing", "paused", "cancelled", "failed", "stale"],
  auditing:["repairing", "rechecking", "pending_confirmation", "paused", "failed", "stale"],
  repairing:["rechecking", "paused", "failed", "stale"],
  rechecking:["repairing", "pending_confirmation", "paused", "failed", "stale"],
  pending_confirmation:["completed", "queued", "running", "stale", "cancelled"],
  completed:["queued", "running", "stale"],
  paused:["queued", "running", "cancelled", "stale"],
  cancelled:["queued", "running", "stale"],
  failed:["queued", "running", "cancelled", "stale"],
  stale:["queued", "running", "cancelled"],
  skipped:["queued", "running", "stale"],
};

export function isProductionTransitionAllowed(from:ProductionStatus, to:ProductionStatus) {
  return from === to || allowedTransitions[from].includes(to);
}

export function createProductionStore(initial:readonly ProductionScopeRecord[] = []) {
  const state = reactive({ records:[...initial] as ProductionScopeRecord[] });

  function replaceSnapshot(records:readonly ProductionScopeRecord[]) {
    state.records = [...records];
  }

  function hydrate(records:readonly ProductionScopeRecord[]) {
    state.records = mergeProductionScopeRecords(state.records, records);
  }

  function transition(key:string, status:ProductionStatus, patch:Partial<ProductionScopeRecord> = {}) {
    const index = state.records.findIndex(record => productionScopeKey(record) === key);
    if (index < 0) throw new Error(`生产范围不存在：${key}`);
    const current = state.records[index];
    if (!isProductionTransitionAllowed(current.status, status)) throw new Error(`非法生产状态转换：${current.status} → ${status}`);
    state.records[index] = { ...current, ...patch, status, updated_at:new Date().toISOString() };
    return state.records[index];
  }

  function stageRecords(projectId:string, stage:string) {
    return state.records.filter(record => record.project_id === projectId && record.stage === stage);
  }

  function aggregateStage(projectId:string, stage:string):AggregatedProductionStatus {
    return aggregateProductionStatus(stageRecords(projectId, stage));
  }
  function aggregateStageProgress(projectId:string, stage:string) { return aggregateProductionProgress(stageRecords(projectId, stage)); }

  function snapshot() {
    return state.records.map(record => ({ ...record }));
  }

  return { state, replaceSnapshot, hydrate, transition, stageRecords, aggregateStage, aggregateStageProgress, snapshot };
}

export type ProductionStore = ReturnType<typeof createProductionStore>;
