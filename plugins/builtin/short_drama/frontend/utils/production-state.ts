import type { AggregatedProductionStatus, ProductionScopeRecord, ProductionStatus } from "../types/production";

const runningStatuses = new Set<ProductionStatus>(["queued", "running", "auditing", "repairing", "rechecking"]);

export function isRunningProductionStatus(status:ProductionStatus) {
  return runningStatuses.has(status);
}

export function aggregateProductionStatus(records:readonly ProductionScopeRecord[]):AggregatedProductionStatus {
  if (!records.length) return "idle";
  if (records.some(record => record.status === "failed")) return "failed";
  if (records.some(record => record.status === "paused")) return "paused";
  if (records.some(record => isRunningProductionStatus(record.status))) return "running";
  if (records.some(record => record.status === "pending_confirmation")) return "pending_confirmation";
  if (records.some(record => record.status === "stale")) return "stale";
  if (records.every(record => record.status === "completed" || record.status === "skipped")) return "completed";
  return "idle";
}

export function productionScopeKey(record:Pick<ProductionScopeRecord, "project_id" | "stage" | "scope_type" | "scope_id">) {
  return `${record.project_id}:${record.stage}:${record.scope_type}:${record.scope_id}`;
}

export function mergeProductionScopeRecords(current:readonly ProductionScopeRecord[], incoming:readonly ProductionScopeRecord[]) {
  const records = new Map(current.map(record => [productionScopeKey(record), record]));
  for (const record of incoming) {
    const key = productionScopeKey(record);
    const previous = records.get(key);
    if (!previous || Date.parse(record.updated_at) >= Date.parse(previous.updated_at)) records.set(key, record);
  }
  return [...records.values()];
}

export function createProductionScopeRecord(input:Omit<ProductionScopeRecord, "created_at" | "updated_at" | "confirmation_scope" | "impact_scope"> & Partial<Pick<ProductionScopeRecord, "created_at" | "updated_at" | "confirmation_scope" | "impact_scope">>, now = new Date().toISOString()):ProductionScopeRecord {
  return {
    ...input,
    completed_count:Math.max(0, Number(input.completed_count) || 0),
    total_count:Math.max(0, Number(input.total_count) || 0),
    confirmation_scope:input.confirmation_scope || { scope_type:input.scope_type, scope_ids:[input.scope_id] },
    impact_scope:input.impact_scope || [],
    created_at:input.created_at || now,
    updated_at:input.updated_at || now,
  };
}

export function aggregateProductionProgress(records:readonly ProductionScopeRecord[]) {
  const completed = records.reduce((total, record) => total + Math.min(record.total_count, record.completed_count), 0);
  const total = records.reduce((sum, record) => sum + record.total_count, 0);
  return { status:aggregateProductionStatus(records), completed, total, label:`${completed}/${total}` };
}

export function createEpisodeBatches(totalEpisodes:number, firstEpisodeStandalone = true, minimum = 3, maximum = 5) {
  const total = Math.max(0, Math.floor(totalEpisodes));
  const batches:Array<{ id:string; start:number; end:number; episodes:number[]; first_episode_standalone:boolean }> = [];
  let start = 1;
  if (firstEpisodeStandalone && total > 0) {
    batches.push({ id:"episode-batch:1", start:1, end:1, episodes:[1], first_episode_standalone:true });
    start = 2;
  }
  while (start <= total) {
    const remaining = total - start + 1;
    let size = Math.min(maximum, remaining);
    if (remaining > maximum && remaining - size < minimum) size -= minimum - (remaining - size);
    const end = start + size - 1;
    batches.push({ id:`episode-batch:${start}-${end}`, start, end, episodes:Array.from({ length:size }, (_, index) => start + index), first_episode_standalone:false });
    start = end + 1;
  }
  return batches;
}

export function createStoryArcBatches(arcs:readonly unknown[], totalEpisodes:number) {
  const total = Math.max(1, Math.floor(totalEpisodes));
  const normalized = arcs.map((value, index) => {
    const arc = value as { start_episode?:unknown; end_episode?:unknown; title?:unknown };
    return { index:index + 1, start:Number(arc?.start_episode), end:Number(arc?.end_episode), title:String(arc?.title || `剧情单元${index + 1}`) };
  }).filter(arc => Number.isInteger(arc.start) && Number.isInteger(arc.end) && arc.start >= 1 && arc.end >= arc.start && arc.end <= total)
    .sort((left, right) => left.start - right.start);
  const continuous = normalized.length > 0 && normalized[0].start === 1
    && normalized.at(-1)?.end === total
    && normalized.every((arc, index) => index === 0 || arc.start === normalized[index - 1].end + 1);
  const source = continuous ? normalized : narrativeAuditRanges("script", total).map((range, index) => ({ index:index + 1, ...range, title:`剧情单元${index + 1}` }));
  return source.map(arc => ({ id:`story-arc:${arc.index}:${arc.start}-${arc.end}`, title:arc.title, start:arc.start, end:arc.end, episodes:Array.from({ length:arc.end - arc.start + 1 }, (_, index) => arc.start + index) }));
}

export function narrativeAuditRanges(target:"outline" | "script" | "storyboard", totalEpisodes:number) {
  const total = Math.max(1, Math.floor(totalEpisodes));
  if (target === "outline" || total <= 3) return [{ start:1, end:total }];
  const ranges = [{ start:1, end:3 }];
  for (let start = 4; start <= total; start += 5) ranges.push({ start, end:Math.min(total, start + 4) });
  return ranges;
}

export function resolveProductionScopeStatus(input:{
  requirement?:boolean;
  requirementComplete?:boolean;
  skipped?:boolean;
  confirmed?:boolean;
  failed?:boolean;
  paused?:boolean;
  running?:boolean;
  runningAudit?:boolean;
  pendingConfirmation?:boolean;
  stale?:boolean;
  narrative?:boolean;
  narrativeAuditRunning?:boolean;
  narrativeAuditCompleted?:boolean;
  transitionQueued?:boolean;
  index:number;
  completed:number;
}):ProductionStatus {
  if (input.requirement) return input.requirementComplete ? "completed" : "idle";
  if (input.skipped) return "skipped";
  if (input.confirmed) return "completed";
  if (input.failed) return "failed";
  if (input.paused) return input.index < input.completed ? "pending_confirmation" : "paused";
  if (input.running) {
    if (input.index < input.completed) return input.pendingConfirmation ? "pending_confirmation" : "auditing";
    if (input.index === input.completed) return input.runningAudit ? "auditing" : "running";
    return "queued";
  }
  if (input.pendingConfirmation) return "pending_confirmation";
  if (input.stale) return "stale";
  if (input.index < input.completed) {
    if (!input.narrative) return "pending_confirmation";
    if (input.narrativeAuditRunning) return "auditing";
    return input.narrativeAuditCompleted ? "pending_confirmation" : "idle";
  }
  if (input.transitionQueued) return "queued";
  return "idle";
}
