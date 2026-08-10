export const qwenVoicePresets = ["Aiden", "Dylan", "Eric", "Ono_Anna", "Ryan", "Serena", "Sohee", "Uncle_Fu", "Vivian"] as const;

export type BusinessShotType = "reaction" | "action" | "dialog" | "atmosphere" | "performance";

type MediaPlanningShot = {
  shot_number:number;
  start_second:number;
  end_second:number;
  shot_size:string;
  visual:string;
  action:string;
  dialogue:string;
};

export function dialogueVoicePlan(shot:Pick<MediaPlanningShot, "dialogue" | "action" | "visual">, characterNames:string[] = []) {
  const dialogue = shot.dialogue.trim();
  const speakerMatch = dialogue.match(/^\s*([^：:\n]{1,24}?)(?:[（(]([^）)]{1,24})[）)])?\s*[：:]\s*([\s\S]+)$/);
  const scene = `${shot.visual || ""} ${shot.action || ""}`;
  const namedCharacter = characterNames.find(name => scene.includes(name));
  const roleMatch = scene.match(/([\p{Script=Han}]{1,10}(?:小姐|先生|女士|导师|店主|经理|医生|父亲|母亲|同事|黑衣人))/u);
  const pronounCharacter = /(?:^|[，。；\s])她|自己|镜中的自己/.test(scene) ? characterNames[0] : undefined;
  const characterName = speakerMatch?.[1]?.trim() || namedCharacter || roleMatch?.[1] || pronounCharacter || "旁白";
  const spokenText = speakerMatch?.[3]?.trim() || dialogue;
  const context = `${speakerMatch?.[2] || ""} ${shot.action || ""} ${shot.visual || ""} ${spokenText}`;
  const emotionKeywords = ["暴怒", "愤怒", "悲伤", "哽咽", "哭泣", "冷笑", "嘲讽", "讥讽", "紧张", "恐惧", "惊讶", "震惊", "温柔", "鼓励", "开心", "激动", "严肃", "低沉", "虚弱", "焦急", "坚定", "自信", "冷静", "克制", "低语", "低声"];
  const expectedEmotion = emotionKeywords.find(keyword => context.includes(keyword)) || "自然";
  let hash = 2166136261;
  for (const character of characterName) { hash ^= character.charCodeAt(0); hash = Math.imul(hash, 16777619); }
  const femaleRole = /小姐|女士|母亲|婉|晴|清|婷|苏|林/.test(characterName);
  const olderMaleRole = /导师|店主|父亲|林父|叔|伯|爷/.test(characterName);
  const pool = femaleRole ? ["Serena", "Vivian", "Ono_Anna", "Sohee"] : olderMaleRole ? ["Uncle_Fu", "Ryan", "Eric"] : ["Aiden", "Dylan", "Eric", "Ryan"];
  const speaker = pool[(hash >>> 0) % pool.length];
  const emotionInstruction = expectedEmotion === "自然"
    ? "自然真实的中文影视对白，准确使用停顿和重音，避免播音腔，保持角色音色稳定。"
    : `以${expectedEmotion}的情绪演绎中文影视对白；根据标点控制停顿，根据剧情调整语速、音量和重音，情绪清晰但不过度，保持角色音色稳定。`;
  return { characterName, spokenText, speaker, expectedEmotion, emotionInstruction };
}

export function classifyBusinessShot(shot:Pick<MediaPlanningShot, "dialogue" | "shot_size" | "visual" | "action">):BusinessShotType {
  if (shot.dialogue?.trim() && !/^无[。.]?$/.test(shot.dialogue.trim())) return "dialog";
  if (/空镜|环境|远景|全景|静止|停顿/.test(`${shot.shot_size} ${shot.visual} ${shot.action}`)) return "atmosphere";
  if (/特写|反应|回头|眨眼|抬眼/.test(`${shot.shot_size} ${shot.action}`)) return "reaction";
  if (/连续|表演|走|跑|打|追|推|拉|转身/.test(shot.action || "")) return "action";
  return "performance";
}

export function buildShotRenderChunks(shot:Pick<MediaPlanningShot, "shot_number" | "start_second" | "end_second">) {
  const duration = Math.max(1, Math.min(10, Number((shot.end_second - shot.start_second).toFixed(3))));
  const chunks:Array<{chunk_id:string; duration:number; overlap_seconds:number}> = [];
  let remaining = duration;
  let index = 0;
  while (remaining > 0.001) {
    const chunkDuration = Number(Math.min(3, remaining).toFixed(3));
    chunks.push({ chunk_id:`shot_${String(shot.shot_number).padStart(2, "0")}-${index}`, duration:chunkDuration, overlap_seconds:index ? Math.min(0.2, Number((chunkDuration / 4).toFixed(3))) : 0 });
    remaining = Number((remaining - chunkDuration).toFixed(3));
    index += 1;
  }
  return chunks;
}
