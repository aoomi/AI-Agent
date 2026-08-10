export type GenerationRetryOptions<T> = {
  execute:(attempt:number, previousError:string) => Promise<T>;
  maxAttempts?:number;
  fallbackError:string;
  onRetry?:(attempt:number, previousError:string) => void | Promise<void>;
  retryDelayMs?:(attempt:number) => number;
};

export async function runGenerationRetry<T>({
  execute,
  maxAttempts = 3,
  fallbackError,
  onRetry,
  retryDelayMs = attempt => Math.min(4000, attempt * 800),
}:GenerationRetryOptions<T>):Promise<T> {
  let lastError = "";
  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    try {
      if (attempt > 1) {
        await onRetry?.(attempt, lastError);
        const delay = retryDelayMs(attempt);
        if (delay > 0) await new Promise(resolve => setTimeout(resolve, delay));
      }
      return await execute(attempt, lastError);
    } catch (error) {
      if ((error as Error)?.name === "AbortError") throw error;
      lastError = String((error as Error)?.message || error);
    }
  }
  throw new Error(lastError || fallbackError);
}
