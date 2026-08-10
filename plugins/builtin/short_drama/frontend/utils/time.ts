export function formatShotTime(value:number) {
  const seconds = Math.max(0, Number(value) || 0);
  return `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(Math.round(seconds % 60)).padStart(2, "0")}`;
}

export function formatRealDuration(value?:number | null) {
  if (!value || value < 1) return "未记录";
  const seconds = Math.max(1, Math.round(value / 1000));
  if (seconds < 60) return `${seconds}秒`;
  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;
  return remainder ? `${minutes}分${remainder}秒` : `${minutes}分钟`;
}

export function formatMinutesOnly(value?:number | null) {
  if (!value || value < 1) return "未记录";
  const minutes = Math.max(0.1, Math.round(value / 6000) / 10);
  return `${Number.isInteger(minutes) ? minutes.toFixed(0) : minutes.toFixed(1)}分钟`;
}
