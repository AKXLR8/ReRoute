import type { AuditLog } from './api';

const CSV_COLS: (keyof AuditLog)[] = [
  'timestamp', 'status_code', 'provider', 'model_requested', 'model_served',
  'fallback_from', 'retry_count', 'is_stream', 'is_cached', 'cache_saved_usd',
  'input_tokens', 'output_tokens', 'cost_usd', 'latency_ms', 'ttft_ms',
  'tokens_per_sec', 'finish_reason', 'trace_id', 'error_message',
];

export function toCsv(rows: AuditLog[]): string {
  const cell = (v: unknown) => {
    const s = v == null ? '' : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  return [CSV_COLS.join(','), ...rows.map((l) => CSV_COLS.map((c) => cell(l[c])).join(','))].join('\r\n');
}
