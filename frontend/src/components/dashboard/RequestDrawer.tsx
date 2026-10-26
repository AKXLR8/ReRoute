import { useState, type ReactNode } from 'react';
import { Check, Copy, X } from 'lucide-react';
import { API_URL, displayColor, displayName, type AuditLog } from '../../lib/api';
import { statusOf, useEscape } from '../../lib/utils';
import { CopyField } from '../ui/CopyField';

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-4 py-2.5 border-b border-[var(--border)] last:border-0">
      <span className="text-[12px] text-[var(--text-muted)] shrink-0">{label}</span>
      <span className="text-[12px] text-[var(--text-primary)] text-right min-w-0 break-words">{children}</span>
    </div>
  );
}

function CopyButton({ value, label = 'Copy' }: { value: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      // clipboard blocked - the block stays selectable
    }
  };
  return (
    <button
      type="button"
      onClick={copy}
      className="h-7 px-2 rounded-md flex items-center gap-1.5 text-[11px] font-medium text-[var(--text-muted)] hover:text-white hover:bg-[var(--hover)] transition-colors shrink-0"
    >
      {copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
      {copied ? 'Copied' : label}
    </button>
  );
}

export function RequestDrawer({ log, onClose }: { log: AuditLog | null; onClose: () => void }) {
  useEscape(!!log, onClose);
  if (!log) return null;

  const st = statusOf(log);
  const model = log.model_requested || log.model_served;
  const body = JSON.stringify({
    model,
    messages: [{ role: 'user', content: 'Your prompt here' }],
  });
  const curl = `curl ${API_URL}/v1/chat/completions \\
  -H "Authorization: Bearer $REROUTE_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '${body}'`;

  return (
    <div className="fixed inset-0 z-[100] bg-black/60" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Request detail"
        className="fixed inset-y-0 right-0 w-full max-w-md overflow-y-auto bg-[var(--bg-card)] border-l border-[var(--border)] shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="sticky top-0 z-10 flex items-start justify-between gap-3 px-5 py-4 border-b border-[var(--border)] bg-[var(--bg-card)]">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h2 className="text-[15px] font-bold text-white truncate">Request</h2>
              <span className="text-[11px] font-semibold px-1.5 py-0.5 rounded" style={{ color: st.color, background: 'var(--bg-overlay)' }}>
                {st.label}
              </span>
              {log.is_stream && (
                <span className="text-[10px] font-semibold uppercase tracking-wider text-[var(--purple)]">stream</span>
              )}
            </div>
            <p className="text-[11px] text-[var(--text-muted)] mt-0.5 truncate font-mono">{log.model_served}</p>
          </div>
          <button onClick={onClose} aria-label="Close" className="shrink-0 text-[var(--text-muted)] hover:text-white transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="px-5 py-4 space-y-5">
          <section>
            <h3 className="text-[10px] uppercase tracking-widest text-[var(--text-faint)] mb-1">Route</h3>
            <Field label="Time">
              <span title={new Date(log.timestamp).toLocaleString()}>{new Date(log.timestamp).toLocaleString()}</span>
            </Field>
            <Field label="Provider">
              <span className="inline-flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full" style={{ background: displayColor(log.provider) }} />
                {displayName(log.provider)}
              </span>
            </Field>
            <Field label="Requested model"><span className="font-mono text-[11px]">{log.model_requested}</span></Field>
            <Field label="Served model"><span className="font-mono text-[11px]">{log.model_served}</span></Field>
            {log.fallback_from && (
              <Field label="Failed over from">
                <span className="inline-flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full" style={{ background: displayColor(log.fallback_from) }} />
                  {displayName(log.fallback_from)}
                </span>
              </Field>
            )}
            {log.retry_count > 0 && <Field label="Retries">{log.retry_count}</Field>}
          </section>

          <section>
            <h3 className="text-[10px] uppercase tracking-widest text-[var(--text-faint)] mb-1">Usage</h3>
            <Field label="Tokens">
              <span className="tabular-nums">
                {log.input_tokens.toLocaleString()} in · {log.output_tokens.toLocaleString()} out
              </span>
            </Field>
            <Field label="Cost">
              {log.is_cached ? (
                <span className="text-emerald-400">
                  cache hit{log.cache_saved_usd > 0 ? ` · saved $${log.cache_saved_usd.toFixed(4)}` : ''}
                </span>
              ) : (
                <span className="tabular-nums">${log.cost_usd.toFixed(4)}</span>
              )}
            </Field>
            <Field label="Cache">{log.is_cached ? 'hit' : 'miss'}</Field>
            <Field label="Finish reason">{log.finish_reason ?? '—'}</Field>
          </section>

          <section>
            <h3 className="text-[10px] uppercase tracking-widest text-[var(--text-faint)] mb-1">Timing</h3>
            <Field label="Latency">{Math.round(log.latency_ms)} ms</Field>
            <Field label="Time to first token">{log.ttft_ms != null ? `${Math.round(log.ttft_ms)} ms` : '—'}</Field>
            <Field label="Output speed">{log.tokens_per_sec != null ? `${Math.round(log.tokens_per_sec)} tok/s` : '—'}</Field>
          </section>

          {log.error_message && (
            <section>
              <h3 className="text-[10px] uppercase tracking-widest text-[var(--text-faint)] mb-1">Error</h3>
              <pre className="text-[11px] text-red-300/90 whitespace-pre-wrap break-words bg-black/40 rounded-lg p-3">{log.error_message}</pre>
            </section>
          )}

          {log.trace_id && (
            <section>
              <h3 className="text-[10px] uppercase tracking-widest text-[var(--text-faint)] mb-2">Trace ID</h3>
              <CopyField value={log.trace_id} />
            </section>
          )}

          <section>
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-[10px] uppercase tracking-widest text-[var(--text-faint)]">Reproduce</h3>
              <CopyButton value={curl} label="Copy cURL" />
            </div>
            <pre className="text-[11px] text-[var(--text-secondary)] whitespace-pre-wrap break-words bg-black/40 rounded-lg p-3">{curl}</pre>
            <p className="text-[11px] text-[var(--text-faint)] mt-2">
              Replace <code className="font-mono">$REROUTE_API_KEY</code> with a gateway key from Settings.
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}
