type PollTaskOptions<T> = {
  request:() => Promise<T>;
  isCompleted:(result:T) => boolean;
  failureMessage?:(result:T) => string;
  maximumAttempts:number;
  intervalMs:number;
  timeoutMessage:string;
  signal?:AbortSignal;
  wait?:(milliseconds:number, signal?:AbortSignal) => Promise<void>;
};

export function waitForPollingInterval(milliseconds:number, signal?:AbortSignal) {
  return new Promise<void>((resolve, reject) => {
    const timer = setTimeout(resolve, milliseconds);
    signal?.addEventListener("abort", () => {
      clearTimeout(timer);
      reject(new DOMException("任务已停止", "AbortError"));
    }, { once:true });
  });
}

export async function pollTaskResult<T>(options:PollTaskOptions<T>) {
  const wait = options.wait || waitForPollingInterval;
  for (let attempt = 0; attempt < options.maximumAttempts; attempt += 1) {
    await wait(options.intervalMs, options.signal);
    const result = await options.request();
    const failure = options.failureMessage?.(result);
    if (failure) throw new Error(failure);
    if (options.isCompleted(result)) return result;
  }
  throw new Error(options.timeoutMessage);
}
