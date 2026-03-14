import { appendFileSync, mkdirSync } from "node:fs";
import { join } from "node:path";

export type LogEvent =
  | "intent_parsed"
  | "plan_proposed"
  | "policy_check"
  | "tool_executed"
  | "tool_blocked"
  | "output_saved";

export interface LogEntry {
  timestamp: string;
  event: LogEvent;
  tool?: string;
  args?: Record<string, unknown>;
  intent_ref?: string;
  policy_decision?: "allowed" | "blocked";
  block_reason?: string;
  result_summary?: string;
  duration_ms?: number;
  details?: Record<string, unknown>;
}

let logDir = "";
let logFile = "";

export function initLogger(workspacePath: string): void {
  logDir = join(workspacePath, "logs");
  mkdirSync(logDir, { recursive: true });
  const ts = new Date().toISOString().replace(/[:.]/g, "-");
  logFile = join(logDir, `trace-${ts}.jsonl`);
}

export function log(entry: Omit<LogEntry, "timestamp">): void {
  if (!logFile) return;
  const record: LogEntry = {
    timestamp: new Date().toISOString(),
    ...entry,
  };
  try {
    appendFileSync(logFile, JSON.stringify(record) + "\n");
  } catch {
    // best-effort
  }
}

export function getLogFile(): string {
  return logFile;
}
