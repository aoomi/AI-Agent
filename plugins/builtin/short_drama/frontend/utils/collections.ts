export function uniqueLatestBy<T>(items:T[], key:(item:T) => string) {
  const unique = new Map<string, T>();
  for (const item of items) unique.set(key(item), item);
  return [...unique.values()];
}
