export function reviewEpisodeKey(target:string, episodeNumber:number) {
  return `${target}-${episodeNumber}`;
}

export function reviewShotKey(episodeNumber:number, shotNumber:number, target:"storyboard"|"video" = "storyboard") {
  return `${target}-${episodeNumber}-${shotNumber}`;
}

export function characterAssetReviewKey(characterId:string, assetId:string) {
  return `${characterId}-${assetId}`;
}

export function reviewLabel<T extends string>(states:Record<string, T>, key:string, fallback:T) {
  return states[key] || fallback;
}
