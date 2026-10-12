import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../lib/api';
import { signOut } from '../lib/nav';
import { DashPage, Segmented } from '../components/dashboard/DashPage';
import { ChartCard } from '../components/dashboard/ChartCard';
import { FileText, RefreshCw } from 'lucide-react';

export default function LogsPage() {
  const [days, setDays] = useState(7);

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['activity', days],
    queryFn: () => api.getActivity(days),
  });

  const unauthorized = isError && /401/.test(String(error));
  const rows = data ?? [];

  return (
    <DashPage
      title="Logs"
      sub="Daily request totals across all providers"
      actions={
        <button onClick={() => refetch()} className="h-9 px-4 rounded-lg flex items-center gap-2 text-[13px] font-medium text-[var(--text-secondary)] border border-[var(--border)] hover:bg-[var(--hover)] transition-colors">
          <RefreshCw className="w-3.5 h-3.5" /> Refresh
        </button>
      }
    >

          {isLoading && (
            <div className="space-y-2 mt-6">
              {[0, 1, 2, 3, 4].map((i) => <div key={i} className="skeleton h-[44px] rounded-xl" />)}
            </div>
          )}

          {isError && (
            <div className="card p-6 mt-6 text-center">
              <p className="text-sm font-medium text-white mb-1">
                {unauthorized ? 'Session expired' : 'Could not load logs'}
              </p>
              <p className="text-xs text-[var(--text-muted)] mb-4">
                {unauthorized ? 'Your API key is no longer valid.' : 'Is the backend running?'}
              </p>
              <div className="flex items-center justify-center gap-2">
                {!unauthorized && (
                  <button onClick={() => refetch()} className="h-9 px-4 rounded-lg text-[13px] font-medium text-black bg-[var(--accent)] hover:opacity-90 transition-opacity">
                    Retry
                  </button>
                )}
                <button onClick={signOut} className="h-9 px-4 rounded-lg text-[13px] font-medium text-[var(--text-muted)] border border-[var(--border)] hover:bg-[var(--hover)] hover:text-[var(--text-primary)] transition-colors">
                  Sign out
                </button>
              </div>
            </div>
          )}

          {!isLoading && !isError && (
            <div className="mt-6">
              {rows.length === 0 ? (
                <ChartCard title="Daily totals" action={<Segmented value={days} onChange={setDays} />}>
                  <div className="flex flex-col items-center justify-center h-[200px]">
                    <FileText className="w-8 h-8 text-[var(--text-faint)] mb-3" />
                    <p className="text-[13px] text-[var(--text-muted)]">No data in this window</p>
                  </div>
                </ChartCard>
              ) : (
                <ChartCard title="Daily totals" action={<Segmented value={days} onChange={setDays} />}>
                  <div className="overflow-x-auto">
                    <table className="text-[12px] w-full">
                      <thead>
                        <tr className="text-left text-[10px] uppercase tracking-widest text-[var(--text-faint)] border-b border-[var(--border)]">
                          <th className="px-4 py-2.5 font-medium">Date</th>
                          <th className="px-4 py-2.5 font-medium">Requests</th>
                          <th className="px-4 py-2.5 font-medium">Avg Latency</th>
                          <th className="px-4 py-2.5 font-medium">TTFT</th>
                          <th className="px-4 py-2.5 font-medium">Tok/s</th>
                          <th className="px-4 py-2.5 font-medium">Cost</th>
                          <th className="px-4 py-2.5 font-medium">Saved</th>
                          <th className="px-4 py-2.5 font-medium">Tokens</th>
                        </tr>
                      </thead>
                      <tbody>
                        {rows.map((row) => (
                          <tr key={row.date} className="border-b border-[var(--border)] last:border-0 hover:bg-[rgba(255,255,255,0.02)] transition-colors">
                            <td className="px-4 py-2.5 text-[var(--text-muted)] font-mono text-[11px]">{row.date}</td>
                            <td className="px-4 py-2.5 text-[var(--text-primary)] font-medium">{row.requests.toLocaleString()}</td>
                            <td className="px-4 py-2.5 text-[var(--text-secondary)]">{Math.round(row.avg_latency_ms)}ms</td>
                            <td className="px-4 py-2.5 text-[var(--text-secondary)]">{row.avg_ttft_ms != null ? `${Math.round(row.avg_ttft_ms)}ms` : '—'}</td>
                            <td className="px-4 py-2.5 text-[var(--text-secondary)]">{row.avg_tokens_per_sec != null ? Math.round(row.avg_tokens_per_sec) : '—'}</td>
                            <td className="px-4 py-2.5 text-[var(--text-secondary)]">${row.cost_usd.toFixed(4)}</td>
                            <td className="px-4 py-2.5 text-emerald-400">{row.cache_saved_usd > 0 ? `$${row.cache_saved_usd.toFixed(4)}` : '—'}</td>
                            <td className="px-4 py-2.5 text-[var(--text-muted)] text-[11px]">{(row.input_tokens + row.output_tokens).toLocaleString()}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </ChartCard>
              )}
            </div>
          )}
    </DashPage>
  );
}
