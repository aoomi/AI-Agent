export function episodeNumberFromTitle(title:string) {
  return Number.parseInt(title.match(/\d+/)?.[0] || "0", 10);
}

export function cleanEpisodeType(value:string) {
  const lastPart = String(value || "").split(/[|｜]/).map(item => item.trim()).filter(Boolean).at(-1) || "本集剧本";
  return lastPart.replace(/^第\s*\d+\s*集\s*/, "").replace(/\s*[·・.]\s*\d+\s*$/, "").trim() || "本集剧本";
}
