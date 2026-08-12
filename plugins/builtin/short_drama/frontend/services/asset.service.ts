import { postJson, postJsonIgnoringResponse, requestJson, requestJsonOk } from "./api-client";

export const assetService = {
  generateAssistantImage<T>(body:unknown, signal?:AbortSignal, fallback = "图片生成失败") { return postJson<T>("/api/assistant/images/generate", body, { signal }, fallback); },
  generateCharacter<T>(body:unknown, signal?:AbortSignal, fallback = "人物资产生成失败") { return postJson<T>("/api/characters/generate", body, { signal }, fallback); },
  extractCharacters<T>(body:unknown, signal?:AbortSignal) { return postJson<T>("/api/characters/extract", body, { signal }, "没有提取到有效角色"); },
  characterResult<T>(name:string, identity:{ tenant_id:string; user_id:string; project_id:string }) { return requestJson<T>(`/api/characters/result?${new URLSearchParams({ name, ...identity })}`); },
  stopCharacter(name:string, identity:Record<string, unknown> = {}) { return postJsonIgnoringResponse("/api/characters/stop", { ...identity, name }); },
  generateShot<T>(body:unknown, signal?:AbortSignal, fallback = "镜头画面生成失败") { return postJson<T>("/api/shots/generate", body, { signal }, fallback); },
  repairShot<T>(body:unknown, signal?:AbortSignal, fallback = "镜头画面修复失败") { return postJson<T>("/api/shots/repair", body, { signal }, fallback); },
  semanticAudit<T>(body:unknown, fallback = "镜头画面语义审核失败") { return postJson<T>("/api/shots/semantic-audit", body, {}, fallback); },
  stopImages(body:unknown) { return postJsonIgnoringResponse("/api/images/stop", body); },
  purgeGenerated<T>(body:unknown, signal?:AbortSignal) { return postJson<T>("/api/assets/purge-generated", body, { signal }, "旧图片和任务缓存清理失败"); },
  generate3D<T>(body:unknown, signal?:AbortSignal) { return postJson<T>("/api/assets/3d/generate", body, { signal }, "3D资产生成失败"); },
  status3D<T>(jobId:string, identity:{ tenant_id:string; user_id:string; project_id:string }) {
    return requestJsonOk<T>(`/api/assets/3d/status?${new URLSearchParams({ job_id:jobId, ...identity })}`, undefined, "3D任务状态读取失败");
  },
  confirm3D<T>(body:unknown) { return postJson<T>("/api/assets/3d/confirm", body, {}, "3D资产确认归档失败"); },
  stop3D(jobId:string, identity:Record<string, unknown>) { return postJsonIgnoringResponse("/api/images/stop", { ...identity, name:jobId }); },
};
