export async function runAuditRepairLoop<T>(options:{
  audit:(attempt:number) => Promise<T>;
  passed:(result:T) => boolean;
  repair:(result:T, attempt:number) => Promise<void>;
  failureMessage:(result:T, repairCount:number) => string;
  onPassed?:(result:T, attempt:number) => void | Promise<void>;
  maximumRepairs?:number;
}) {
  const maximumRepairs = options.maximumRepairs ?? 2;
  for (let attempt = 0; attempt <= maximumRepairs; attempt += 1) {
    const result = await options.audit(attempt);
    if (options.passed(result)) {
      await options.onPassed?.(result, attempt);
      return result;
    }
    if (attempt === maximumRepairs) throw new Error(options.failureMessage(result, maximumRepairs));
    await options.repair(result, attempt);
  }
  throw new Error("自动审核修复未得到最终结果");
}
