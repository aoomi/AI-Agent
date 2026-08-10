export function normalizeForSearch(value:string) {
  return value.toLowerCase().replace(/[\s\p{P}\p{S}]+/gu, "");
}

export function contentMatchScore(request:string, content:string) {
  const source = normalizeForSearch(request);
  const target = normalizeForSearch(content);
  if (target.length < 12 || source.length < 12) return 0;
  if (source.includes(target)) return 1;
  const width = 4;
  const sourceParts = new Set(Array.from({ length:Math.max(0, source.length - width + 1) }, (_, index) => source.slice(index, index + width)));
  const targetParts = new Set(Array.from({ length:Math.max(0, target.length - width + 1) }, (_, index) => target.slice(index, index + width)));
  if (!targetParts.size) return 0;
  let overlap = 0;
  targetParts.forEach(part => { if (sourceParts.has(part)) overlap += 1; });
  return overlap / targetParts.size;
}
