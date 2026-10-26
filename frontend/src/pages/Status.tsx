import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { API_URL, displayColor, displayName } from '../lib/api';

interface ProviderStatus {
  name: string;
  health: 'up' | 'down' | 'unknown';
  circuit: string;
  latency_ms: number | null;
}

interface StatusBody {
  service: 'ok' | 'degraded';
  checks: Record<string, string>;
  providers: ProviderStatus[];
  generated_at: string;
}

const CHECK_LABEL: Record<string, string> = { api: 'API', database: 'Database', redis: 'Redis' };
const TONE: Record<string, string> = {
  ok: 'var(--accent)',
  unknown: 'var(--text-faint)',
  error: 'var(--danger)',
  up: 'var(--accent)',
  down: 'var(--danger)',
};

function Dot({ tone }: { tone: string }) {
  return <span className="w-2 h-2 rounded-full shrink-0" style={{ background: tone }} />;
}

export default function Status() {
  const { data, isError, dataUpdatedAt } = useQuery({
    queryKey: ['status'],
    queryFn: async (): Promise<StatusBody> => {
      const res = await fetch(`${API_URL}/status`);
      if (!res.ok) throw new Error(String(res.status));
      return res.json();
    },
    refetchInterval: 15_000,
    staleTime: 0,
  });

  const ok = data?.service === 'ok' && !isError;
  const headline = isError ? 'Status unavailable' : ok ? 'All systems operational' : 'Degraded performance';

  return (
    <div className="container-x py-16 max-w-3xl">
      <p className="text-[11px] uppercase tracking-wider text-[var(--text-faint)]">Status</p>
      <h1 className="text-[26px] font-bold text-white mt-2">Gateway health</h1>
      <p className="text-[14px] text-[var(--text-muted)] mt-2 leading-relaxed">
        Live provider and infrastructure checks, refreshed every 15 seconds. No account data is shown here.
      </p>

      <div className="card p-5 mt-8 flex items-center gap-3">
        <Dot tone={isError ? 'var(--danger)' : ok ? 'var(--accent)' : 'var(--warning)'} />
        <p className="text-[14px] font-semibold text-white">{headline}</p>
        <p className="text-[11px] text-[var(--text-faint)] ml-auto">
          {data && !isError ? `checked ${new Date(dataUpdatedAt).toLocaleTimeString()}` : ''}
        </p>
      </div>

      {data && !isError && (
        <>
          <div className="card p-0 mt-4 overflow-hidden">
            <h2 className="text-[13px] font-semibold text-[var(--text-primary)] px-5 pt-4 pb-2">Infrastructure</h2>
            {Object.entries(data.checks).map(([key, state]) => (
              <div key={key} className="flex items-center gap-3 px-5 py-3 border-t border-[var(--border)]">
                <Dot tone={TONE[state] ?? 'var(--text-faint)'} />
                <span className="text-[13px] text-[var(--text-secondary)]">{CHECK_LABEL[key] ?? key}</span>
                <span className="text-[11px] ml-auto capitalize" style={{ color: state === 'ok' ? 'var(--text-muted)' : TONE[state] }}>
                  {state === 'ok' ? 'operational' : state === 'unknown' ? 'not configured' : 'outage'}
                </span>
              </div>
            ))}
          </div>

          <div className="card p-0 mt-4 overflow-hidden">
            <h2 className="text-[13px] font-semibold text-[var(--text-primary)] px-5 pt-4 pb-2">Providers</h2>
            {data.providers.length === 0 && (
              <p className="px-5 py-6 text-[13px] text-[var(--text-muted)]">No provider checks reported yet.</p>
            )}
            {data.providers.map((p) => (
              <div key={p.name} className="flex items-center gap-3 px-5 py-3 border-t border-[var(--border)]">
                <span className="w-2 h-2 rounded-full shrink-0" style={{ background: displayColor(p.name) }} />
                <span className="text-[13px] text-[var(--text-primary)]">{displayName(p.name)}</span>
                {p.latency_ms != null && (
                  <span className="text-[11px] text-[var(--text-faint)] tabular-nums">{Math.round(p.latency_ms)}ms</span>
                )}
                <span className="ml-auto flex items-center gap-2">
                  {p.circuit !== 'closed' && (
                    <span className="text-[10px] font-semibold uppercase tracking-wider" style={{ color: p.circuit === 'open' ? 'var(--danger)' : 'var(--warning)' }}>
                      circuit {p.circuit.replace('_', ' ')}
                    </span>
                  )}
                  {p.health === 'unknown' ? (
                    <span className="text-[11px] text-[var(--text-faint)]">not monitored</span>
                  ) : (
                    <>
                      <Dot tone={TONE[p.health]} />
                      <span className="text-[11px] capitalize" style={{ color: p.health === 'up' ? 'var(--text-muted)' : TONE[p.health] }}>
                        {p.health}
                      </span>
                    </>
                  )}
                </span>
              </div>
            ))}
          </div>
        </>
      )}

      <p className="text-[12px] text-[var(--text-muted)] mt-8">
        Seeing errors in your own traffic?{' '}
        <Link to="/dashboard/logs" className="text-[var(--accent)] underline underline-offset-2">Open your request logs</Link>
        .
      </p>
    </div>
  );
}
