import { formatMinutesOnly } from "./time.ts";

export type NarrativeTimingStage = "outline" | "script" | "storyboard";

export type NarrativeStageTiming = {
  startedAt:number;
  generationStartedAt:number;
  generationCompletedAt:number;
  firstAuditStartedAt:number;
  firstAuditCompletedAt:number;
  finalAuditStartedAt:number;
  finalAuditCompletedAt:number;
};

export type PersistedGenerationClock = { generationStartedAt:number; generationElapsedSeconds:number };

export function restoreGenerationClock(startedAt = 0, elapsedSeconds = 0, running = false, now = Date.now()):PersistedGenerationClock {
  const safeStartedAt = Math.max(0, Number(startedAt) || 0);
  const safeElapsed = Math.max(0, Number(elapsedSeconds) || 0);
  return {
    generationStartedAt:safeStartedAt,
    generationElapsedSeconds:running && safeStartedAt
      ? Math.max(safeElapsed, Math.floor((now - safeStartedAt) / 1000))
      : safeElapsed,
  };
}

export function freezeGenerationClock(startedAt = 0, elapsedSeconds = 0, now = Date.now()):PersistedGenerationClock {
  return restoreGenerationClock(startedAt, elapsedSeconds, Boolean(startedAt), now);
}

export function createNarrativeStageTiming(startedAt = 0):NarrativeStageTiming {
  return {
    startedAt,
    generationStartedAt:startedAt,
    generationCompletedAt:0,
    firstAuditStartedAt:0,
    firstAuditCompletedAt:0,
    finalAuditStartedAt:0,
    finalAuditCompletedAt:0,
  };
}

export function ensureNarrativeStageTiming(
  timings:Partial<Record<NarrativeTimingStage, NarrativeStageTiming>>,
  target:NarrativeTimingStage,
  reset = false,
  now = Date.now(),
) {
  if (reset || !timings[target]) timings[target] = createNarrativeStageTiming(reset ? now : 0);
  return timings[target]!;
}

export function buildNarrativeTimingReport(target:NarrativeTimingStage, episodeCount:number, timing?:NarrativeStageTiming) {
  const generationMs = timing?.generationCompletedAt && timing.generationStartedAt ? timing.generationCompletedAt - timing.generationStartedAt : 0;
  const firstAuditMs = timing?.firstAuditCompletedAt && timing.firstAuditStartedAt ? timing.firstAuditCompletedAt - timing.firstAuditStartedAt : 0;
  const finalAuditMs = timing?.finalAuditCompletedAt && timing.finalAuditStartedAt ? timing.finalAuditCompletedAt - timing.finalAuditStartedAt : 0;
  const totalMs = generationMs > 0 && firstAuditMs > 0 && finalAuditMs > 0 ? generationMs + firstAuditMs + finalAuditMs : 0;
  const contentLabel = target === "script" ? "全部剧本" : target === "storyboard" ? "全部分镜脚本" : "全部故事大纲";
  const stageLabel = target === "script" ? "生成剧本" : target === "storyboard" ? "分镜脚本" : "故事大纲";
  return [
    `${stageLabel}：共 ${episodeCount} 集`,
    `${contentLabel}：${formatMinutesOnly(totalMs)}`,
    `全部集数：${formatMinutesOnly(generationMs)}`,
    `首次审核：${formatMinutesOnly(firstAuditMs)}`,
    `最终审核：${formatMinutesOnly(finalAuditMs)}`,
  ].join("\n");
}
