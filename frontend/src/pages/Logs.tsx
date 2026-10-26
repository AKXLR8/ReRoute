import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { api, displayColor, displayName, type AuditLog } from '../lib/api';
import { signOut } from '../lib/nav';
import { timeAgo } from '../lib/utils';
import { DashPage, Segmented } from '../components/dashboard/DashPage';
import { ChartCard } from '../components/dashboard/ChartCard';
import { FileText, RefreshCw } from 'lucide-react';

const fmtDay = (d: string) =>
  new Date(`${d}T00:00:00`).toLocaleDateString(undefined, {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
  });

/* cached wins the badge - it is the useful fact even when the cached call was a 200 */
function statusOf(l: AuditLog): { label: string; color: string } {
  if (l.is_cached) return { label: 'cached', color: 'var(--accent)' };
  if (l.status_code === 403) return { label: 'blocked', color: 'var(--danger)' };
  if (l.status_code >= 400) return { label: String(l.status_code), color: 'var(--danger)' };
  return { label: String(l.status_code), color: 'var(--text-faint)' };
}

export default function LogsPage() {
  const [days, setDays] = useState(7);
  const [refreshing, setRefreshing] = useState(false);

  const activity = useQuery({ queryKey: ['activity', days], queryFn: () => api.getActivity(days) });
  const requests = useQuery({ queryKey: ['logs'], queryFn: () => api.listLogs(100) });

  const isError = activity.isError || requests.isError;
  const unauthorized = isError && /401/.test(String(activity.error ?? requests.error));
  const rows = activity.data ?? [];
  const reqs = requests.data ?? [];
  const isLoading = activity.isLoading || requests.isLoading;

  const totals = rows.reduce(
    (acc, r) => ({
      requests: acc.requests + r.requests,
      latency: acc.latency + r.avg_latency_ms * r.requests,
      cost: acc.cost + r.cost_usd,
      saved: acc.saved + r.cache_saved_usd,
      tokens: acc.tokens + r.input_tokens + r.output_tokens,
    }),
    { requests: 0, latency: 0, cost: 0, saved: 0, tokens: 0 },
  );

  const refresh = async () => {
    setRefreshing(true);
    try {
      await Promise.all([activity.refetch(), requests.refetch()]);
    } finally {
      setRefreshing(false);
    }
  };

  return (
    <DashPage
      title="Logs"
      sub="Daily totals and the latest 100 gateway requests"
      actions={
        <button
          onClick={refresh}
          disabled={refreshing}
          className="h-9 px-4 rounded-lg flex items-center gap-2 text-[13px] font-medium text-[var(--text-secondary)] border border-[var(--border)] hover:bg-[var(--hover)] transition-colors disabled:opacity-60 disabled:pointer-events-none"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} /> {refreshing ? 'Refreshing' : 'Refresh'}
        </button>
      }
    >
      {isError && (
        <div className="card p-6 text-center">
          <p className="text-sm font-medium text-white mb-1">
            {unauthorized ? 'Session expired' : 'Could not load logs'}
          </p>
          <p className="text-xs text-[var(--text-muted)] mb-4">
            {unauthorized ? 'Sign in again to reload your traffic.' : 'Could not reach the gateway API.'}
          </p>
          <div className="flex items-center justify-center gap-2">
            {!unauthorized && (
              <button onClick={refresh} className="h-9 px-4 rounded-lg text-[13px] font-medium text-black bg-[var(--accent)] hover:opacity-90 transition-opacity">
                Retry
              </button>
            )}
            <button onClick={signOut} className="h-9 px-4 rounded-lg text-[13px] font-medium text-[var(--text-muted)] border border-[var(--border)] hover:bg-[var(--hover)] hover:text-[var(--text-primary)] transition-colors">
              Sign out
            </button>
          </div>
        </div>
      )}

      {!isError && (
        <div className="space-y-4">
          <ChartCard title="Daily totals" action={<Segmented value={days} onChange={setDays} />}>
            {isLoading ? (
              <div className="px-4 pb-4 mt-2 space-y-2">
                {[0, 1, 2, 3, 4].map((i) => <div key={i} className="skeleton h-[36px] rounded-lg" />)}
              </div>
            ) : rows.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-[200px]">
                <FileText className="w-8 h-8 text-[var(--text-faint)] mb-3" />
                <p className="text-[13px] text-[var(--text-muted)]">No traffic in this window.</p>
                <Link to="/dashboard/settings" className="text-[12px] text-[var(--accent)] hover:underline mt-1">
                  Create a gateway key to send your first request
                </Link>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="text-[12px] w-full min-w-[720px]">
                  <thead>
                    <tr className="text-left text-[10px] uppercase tracking-widest text-[var(--text-faint)] border-b border-[var(--border)]">
                      <th className="px-4 py-2.5 font-medium">Date</th>
                      <th className="px-4 py-2.5 font-medium">Requests</th>
                      <th className="px-4 py-2.5 font-medium">Avg latency</th>
                      <th className="px-4 py-2.5 font-medium">TTFT</th>
                      <th className="px-4 py-2.5 font-medium">Tok/s</th>
                      <th className="px-4 py-2.5 font-medium">Cost</th>
                      <th className="px-4 py-2.5 font-medium">Saved</th>
                      <th className="px-4 py-2.5 font-medium">Tokens</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((row) => (
                      <tr key={row.date} className="border-b border-[var(--border)] hover:bg-[rgba(255,255,255,0.02)] transition-colors">
                        <td className="px-4 py-2.5 text-[var(--text-muted)] font-mono text-[11px] whitespace-nowrap">{fmtDay(row.date)}</td>
                        <td className="px-4 py-2.5 text-[var(--text-primary)] font-medium tabular-nums">{row.requests.toLocaleString()}</td>
                        <td className="px-4 py-2.5 text-[var(--text-secondary)] tabular-nums">{Math.round(row.avg_latency_ms)}ms</td>
                        <td className="px-4 py-2.5 text-[var(--text-secondary)] tabular-nums">{row.avg_ttft_ms != null ? `${Math.round(row.avg_ttft_ms)}ms` : '—'}</td>
                        <td className="px-4 py-2.5 text-[var(--text-secondary)] tabular-nums">{row.avg_tokens_per_sec != null ? Math.round(row.avg_tokens_per_sec) : '—'}</td>
                        <td className="px-4 py-2.5 text-[var(--text-secondary)] tabular-nums">${row.cost_usd.toFixed(4)}</td>
                        <td className="px-4 py-2.5 text-emerald-400 tabular-nums">{row.cache_saved_usd > 0 ? `$${row.cache_saved_usd.toFixed(4)}` : '—'}</td>
                        <td className="px-4 py-2.5 text-[var(--text-muted)] text-[11px] tabular-nums">{(row.input_tokens + row.output_tokens).toLocaleString()}</td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot>
                    <tr className="border-t border-[var(--border-strong)] text-[var(--text-primary)]">
                      <td className="px-4 py-2.5 text-[10px] uppercase tracking-widest text-[var(--text-faint)]">Total</td>
                      <td className="px-4 py-2.5 font-semibold tabular-nums">{totals.requests.toLocaleString()}</td>
                      <td className="px-4 py-2.5 text-[var(--text-secondary)] tabular-nums">
                        {totals.requests ? `${Math.round(totals.latency / totals.requests)}ms` : '—'}
                      </td>
                      <td className="px-4 py-2.5 text-[var(--text-faint)]" colSpan={2}>—</td>
                      <td className="px-4 py-2.5 font-semibold tabular-nums">${totals.cost.toFixed(4)}</td>
                      <td className="px-4 py-2.5 text-emerald-400 font-semibold tabular-nums">${totals.saved.toFixed(4)}</td>
                      <td className="px-4 py-2.5 text-[var(--text-secondary)] tabular-nums">{totals.tokens.toLocaleString()}</td>
                    </tr>
                  </tfoot>
                </table>
              </div>
            )}
          </ChartCard>

          <ChartCard
            title="Recent requests"
            subtitle="Newest first · hover a row for its error detail"
            legend={reqs.length > 0 ? [{ color: 'var(--accent)', label: `${reqs.length} requests` }] : undefined}
          >
            {requests.isLoading ? (
              <div className="px-4 pb-4 mt-2 space-y-2">
                {[0, 1, 2, 3, 4, 5].map((i) => <div key={i} className="skeleton h-[36px] rounded-lg" />)}
              </div>
            ) : reqs.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-[180px]">
                <FileText className="w-8 h-8 text-[var(--text-faint)] mb-3" />
                <p className="text-[13px] text-[var(--text-muted)]">No requests yet.</p>
                <Link to="/docs" className="text-[12px] text-[var(--accent)] hover:underline mt-1">
                  See the quickstart
                </Link>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="text-[12px] w-full min-w-[760px]">
                  <thead>
                    <tr className="text-left text-[10px] uppercase tracking-widest text-[var(--text-faint)] border-b border-[var(--border)]">
                      <th className="px-4 py-2.5 font-medium">Time</th>
                      <th className="px-4 py-2.5 font-medium">Model</th>
                      <th className="px-4 py-2.5 font-medium">Provider</th>
                      <th className="px-4 py-2.5 font-medium">Status</th>
                      <th className="px-4 py-2.5 font-medium">Tokens</th>
                      <th className="px-4 py-2.5 font-medium">Cost</th>
                      <th className="px-4 py-2.5 font-medium">Latency</th>
                      <th className="px-4 py-2.5 font-medium">TTFT</th>
                    </tr>
                  </thead>
                  <tbody>
                    {reqs.map((l) => {
                      const st = statusOf(l);
                      const abs = new Date(l.timestamp).toLocaleString();
                      return (
                        <tr
                          key={l.id}
                          title={`${abs}${l.error_message ? `\n${l.error_message}` : ''}`}
                          className="border-b border-[var(--border)] last:border-0 hover:bg-[rgba(255,255,255,0.02)] transition-colors"
                        >
                          <td className="px-4 py-2.5 text-[var(--text-muted)] whitespace-nowrap">{timeAgo(l.timestamp)}</td>
                          <td className="px-4 py-2.5 font-mono text-[11px] text-[var(--text-primary)] max-w-[220px] truncate">{l.model_served}</td>
                          <td className="px-4 py-2.5 text-[var(--text-secondary)] whitespace-nowrap">
                            <span className="inline-flex items-center gap-1.5">
                              <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: displayColor(l.provider) }} />
                              {displayName(l.provider)}
                            </span>
                          </td>
                          <td className="px-4 py-2.5 font-medium whitespace-nowrap" style={{ color: st.color }}>{st.label}</td>
                          <td className="px-4 py-2.5 text-[var(--text-muted)] tabular-nums">{(l.input_tokens + l.output_tokens).toLocaleString()}</td>
                          <td className="px-4 py-2.5 tabular-nums" style={{ color: l.is_cached ? 'var(--accent)' : 'var(--text-secondary)' }}>
                            {l.is_cached ? (l.cache_saved_usd > 0 ? `saved $${l.cache_saved_usd.toFixed(4)}` : 'free') : `$${l.cost_usd.toFixed(4)}`}
                          </td>
                          <td className="px-4 py-2.5 text-[var(--text-secondary)] tabular-nums">{Math.round(l.latency_ms)}ms</td>
                          <td className="px-4 py-2.5 text-[var(--text-secondary)] tabular-nums">{l.ttft_ms != null ? `${Math.round(l.ttft_ms)}ms` : '—'}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </ChartCard>
        </div>
      )}
    </DashPage>
  );
}
