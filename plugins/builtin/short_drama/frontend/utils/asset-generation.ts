export const portraitImageRequest = Object.freeze({ width:928, height:1664 });

type CharacterIdentity = { name:string; role:string; imagePrompt:string; appearance:string };

type ShotPromptInput = {
  visual:string;
  action:string;
  scene:string;
  shot_size:string;
  camera:string;
};

export function characterDisplayName(character:Pick<CharacterIdentity, "name" | "role">) {
  const role = character.role.trim();
  return role && role !== character.name ? `${role} · ${character.name}` : character.name;
}

export function isMainCharacter(character:Pick<CharacterIdentity, "name" | "role">) {
  return /主角|男主|女主|第一主角|核心主角/.test(character.role);
}

export function scriptOccurrenceCount(contents:string[], name:string) {
  const source = contents.join("\n");
  return name ? source.split(name).length - 1 : 0;
}

export function characterDetailsText(character:Pick<CharacterIdentity, "appearance">) {
  return `外貌：${character.appearance}`;
}

export function canonicalCharacterVisualRule(character:Pick<CharacterIdentity, "name" | "role">) {
  const identity = `${character.name} ${character.role}`;
  if (/孙悟空|美猴王|齐天大圣/.test(identity)) return "最高优先级物种硬约束：拟人石猴，必须看见明确猴脸、前突猴口鼻、外露猴耳、面部与身体金棕色短毛、灵长类体态和手足。绝对禁止光滑人类脸、普通男性脸、纯人类古装武将。";
  if (/猪八戒|天蓬元帅/.test(identity)) return "最高优先级物种硬约束：拟人猪妖，必须看见猪首、猪耳、突出猪鼻和粗壮体态。绝对禁止普通人类脸。";
  return "";
}

export function buildCharacterBaselinePrompt(character:CharacterIdentity) {
  return `${canonicalCharacterVisualRule(character)}\n${character.imagePrompt}\n${characterDetailsText(character)}\n0°正面全身基准图，独立单张生成。`;
}

export function buildCharacterAssetPrompt(character:CharacterIdentity, promptSuffix:string, baselineLocked = false) {
  const baselineRule = baselineLocked
    ? "唯一身份与造型基准：输入的0°正面全身照。必须原样锁定同一人物的脸型、五官比例、肤色、毛色、年龄、体型、发型、头冠与全部配饰、服装结构纹样与颜色、披风、鞋靴和随身武器；只允许改变指定视角和景别，禁止重新设计、增删或替换任何造型元素。"
    : "";
  return `${baselineRule}\n${canonicalCharacterVisualRule(character)}\n${character.imagePrompt}\n${characterDetailsText(character)}\n独立单张角色定妆资产：${promptSuffix}。纯中性无缝背景，单一人物，身份、年龄、体型、五官、妆发、服装、配饰、道具和色彩保持一致。9:16竖画幅，主体完整，无多角度拼图，无文字、商标、二维码和水印。`;
}

export function buildShotImagePrompt(input:{
  shot:ShotPromptInput;
  characterNames:string[];
  lockedAssetNames:string[];
  style:string;
}) {
  const compact = (value:string, limit:number) => value.replace(/\s+/g, " ").trim().slice(0, limit);
  return [
    `主体人物：${input.characterNames.join("、") || "无指定人物"}`,
    `人物与动作：${compact(`${input.shot.visual} ${input.shot.action}`, 420)}`,
    `场景环境：${compact(input.shot.scene, 160)}`,
    `镜头构图：${compact(`${input.shot.shot_size}，${input.shot.camera}`, 160)}`,
    `资产约束：${input.lockedAssetNames.length ? `必须复用人物场景库中的${input.lockedAssetNames.join("、")}，保持身份、空间布局、材质与外观一致` : "当前人物、场景和道具均为单次内容，只按本分镜临时生成，不建立复用资产"}`,
    `视觉风格：${compact(input.style, 100)}，电影光影，影视3D渲染`,
  ].filter(Boolean).join("\n");
}
