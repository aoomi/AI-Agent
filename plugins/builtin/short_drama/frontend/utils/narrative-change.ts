export type NarrativeChangeType = "none" | "formatting" | "typo" | "subtitle" | "visual" | "duration" | "semantic";

function compact(value:string) {
  return value.normalize("NFKC").replace(/[\s\p{P}]/gu, "");
}

function editDistance(left:string, right:string) {
  const previous = Array.from({ length:right.length + 1 }, (_, index) => index);
  for (let row = 1; row <= left.length; row += 1) {
    let diagonal = previous[0];
    previous[0] = row;
    for (let column = 1; column <= right.length; column += 1) {
      const upper = previous[column];
      previous[column] = Math.min(previous[column] + 1, previous[column - 1] + 1, diagonal + (left[row - 1] === right[column - 1] ? 0 : 1));
      diagonal = upper;
    }
  }
  return previous[right.length];
}

export function classifyNarrativeChange(before:string, after:string):NarrativeChangeType {
  if (before === after) return "none";
  const beforeCompact = compact(before);
  const afterCompact = compact(after);
  if (beforeCompact === afterCompact) return "formatting";
  const combined = `${before}\n${after}`;
  if (/(字幕|SRT|字体|字号|描边|透明度|字色)/iu.test(combined)) return "subtitle";
  if (/(时长|秒|分钟|语速|配音|音频|停顿|口型)/u.test(combined)) return "duration";
  if (/(镜头|景别|运镜|构图|服装|场景|光线|画面|色调)/u.test(combined)) return "visual";
  const maximum = Math.max(beforeCompact.length, afterCompact.length, 1);
  const distance = editDistance(beforeCompact, afterCompact);
  if (distance <= 2 || distance / maximum <= 0.02) return "typo";
  return "semantic";
}

export function changeTypeLabel(type:NarrativeChangeType) {
  return ({ none:"无变更", formatting:"纯排版", typo:"错别字", subtitle:"字幕呈现", visual:"视觉", duration:"时长/音频", semantic:"语义" } as const)[type];
}
