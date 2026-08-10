import { postJson, postJsonIgnoringResponse, requestJson } from "./api-client";

export const mediaService = {
  faceAudit<T>(body:unknown, fallback = "人物一致性审核失败") { return postJson<T>("/api/videos/face-consistency-audit", body, {}, fallback); },
  continuityAudit<T>(body:unknown) { return postJson<T>("/api/videos/continuity-audit", body, {}, "相邻镜头连续性审核失败"); },
  generateVideo<T>(body:unknown, signal?:AbortSignal) { return postJson<T>("/api/videos/generate", body, { signal }, "视频任务提交失败"); },
  videoResult<T>(identity:{ tenant_id:string; user_id:string; project_id:string }, episode:number, shotNumber:number, signal?:AbortSignal) {
    return requestJson<T>(`/api/videos/result?${new URLSearchParams({ ...identity, episode:String(episode), shot_number:String(shotNumber) })}`, { signal });
  },
  stopVideos(body:unknown) { return postJsonIgnoringResponse("/api/videos/stop", body); },
  tts<T>(body:unknown) { return postJson<T>("/api/audio/tts", body, {}, "配音生成失败"); },
  speakerAudit<T>(body:unknown) { return postJson<T>("/api/audio/speaker-audit", body, {}, "角色声纹审核失败"); },
  emotionAudit<T>(body:unknown) { return postJson<T>("/api/audio/emotion-audit", body, {}, "对白情绪审核失败"); },
  audioRepair<T>(body:unknown) { return postJson<T>("/api/videos/audio-repair", body, {}, "局部音频混音失败"); },
  lipSync<T>(body:unknown) { return postJson<T>("/api/videos/lipsync", body, {}, "口型生成失败"); },
  lipSyncAudit<T>(body:unknown, fallback = "口型审核失败") { return postJson<T>("/api/videos/lipsync-audit", body, {}, fallback); },
  latentSync<T>(body:unknown, fallback:string) { return postJson<T>("/api/videos/latentsync", body, {}, fallback); },
  merge<T>(body:unknown, signal?:AbortSignal) { return postJson<T>("/api/videos/merge", body, { signal }, "合并成片失败"); },
  finalAudit<T>(body:unknown, signal?:AbortSignal) { return postJson<T>("/api/videos/audit", body, { signal }, "成片审核失败"); },
  repairPlan<T>(body:unknown) { return postJson<T>("/api/repair/plan", body, {}, "修复计划生成失败"); },
  retakeWindow<T>(body:unknown) { return postJson<T>("/api/videos/retake-window", body, {}, "视频时间窗修复失败"); },
  subtitleTextAudit<T>(body:unknown, signal?:AbortSignal) { return postJson<T>("/api/subtitles/text-audit", body, { signal }); },
  subtitleOcrAudit<T>(body:unknown, signal?:AbortSignal) { return postJson<T>("/api/subtitles/ocr-audit", body, { signal }); },
  subtitleSpeechAudit<T>(body:unknown, signal?:AbortSignal) { return postJson<T>("/api/subtitles/speech-audit", body, { signal }); },
  reburnSubtitles<T>(body:unknown) { return postJson<T>("/api/videos/subtitles/reburn", body, {}, "字幕重新烧录失败"); },
  upscale<T>(body:unknown) { return postJson<T>("/api/videos/upscale", body, {}, "超分降噪失败"); },
  imageUpscale<T>(body:unknown) { return postJson<T>("/api/images/upscale", body, {}, "图片超分失败"); },
  identityRefine<T>(body:unknown) { return postJson<T>("/api/images/identity-refine", body, {}, "人物身份修正失败"); },
  upscaleQuote<T>(body:unknown) { return postJson<T>("/api/videos/upscale/quote", body, {}, "增强价格试算失败"); },
  importedMediaAudit<T>(body:unknown) { return postJson<T>("/api/videos/import-audit", body, {}, "导入媒体审核失败"); },
  createExport<T>(body:unknown, signal?:AbortSignal) { return postJson<T>("/api/exports/create", body, { signal }, "成果导出失败"); },
};
