export type SequentialGenerationOptions<T> = {
  start:number;
  total:number;
  beforeEpisode?:(episode:number) => void | Promise<void>;
  generate:(episode:number) => Promise<T>;
  commit:(episode:number, result:T) => void | Promise<void>;
};

export async function runSequentialGeneration<T>(options:SequentialGenerationOptions<T>) {
  const start = Math.max(1, Math.floor(options.start));
  const total = Math.max(0, Math.floor(options.total));
  let completed = start - 1;
  for (let episode = start; episode <= total; episode += 1) {
    await options.beforeEpisode?.(episode);
    const result = await options.generate(episode);
    await options.commit(episode, result);
    completed = episode;
  }
  return completed;
}
