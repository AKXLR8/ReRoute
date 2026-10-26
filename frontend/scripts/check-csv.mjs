import assert from 'node:assert/strict';
import { toCsv } from '../src/lib/csv.ts';

const log = {
  id: '1', timestamp: '2026-10-01T00:00:00Z', status_code: 200,
  provider: 'openai', model_requested: 'gpt-4o', model_served: 'gpt-4o',
  fallback_from: null, retry_count: 0, is_stream: false, is_cached: false,
  cache_saved_usd: 0, input_tokens: 10, output_tokens: 5, cost_usd: 0.01,
  latency_ms: 120, ttft_ms: null, tokens_per_sec: null, finish_reason: 'stop',
  trace_id: null, error_message: 'boom, "quoted"\nline',
};

const lines = toCsv([log]).split('\r\n');
assert.equal(lines.length, 2);
assert.ok(lines[0].startsWith('timestamp,status_code,provider'));
assert.ok(lines[1].includes('"boom, ""quoted""\nline"'));
assert.equal(toCsv([]).split('\r\n').length, 1);

console.log('csv ok');
