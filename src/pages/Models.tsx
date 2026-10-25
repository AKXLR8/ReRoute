import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Search, Cpu, ArrowUpDown, ExternalLink, RefreshCw } from 'lucide-react';
import { api, displayName, displayColor } from '../lib/api';
import { fetchMarket, modelUrl, providerUrl } from '../lib/pricing';
import { brandLogo, filteredLogo, wideLogo } from '../lib/logos';
import { cn } from '../lib/utils';
import { DashPage } from '../components/dashboard/DashPage';
import { ChartCard } from '../components/dashboard/ChartCard';

/* ponytail: only providers with a real glyph get one; the rest keep Cpu */
const logoSlug: Record<string, string> = {
  openai: 'openai',
  anthropic: 'anthropic',
  gemini: 'googlegemini',
  groq: 'groq',
  ollama: 'ollama',
};

type SortKey = 'id' | 'provider';

export default function Models() {
  const [search, setSearch] = useState('');
  const [provider, setProvider] = useState('All');
  const [sortKey, setSortKey] = useState<SortKey>('provider');
  const [sortAsc, setSortAsc] = useState(true);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['models'],
    queryFn: api.listModels,
  });
  // market feed (shared 24h cache) — gives every model its pricing page link
  const market = useQuery({ queryKey: ['pricing'], queryFn: fetchMarket, staleTime: 24 * 60 * 60 * 1000, retry: 1 });

  const models = data?.data ?? [];
  const urls = useMemo(() => {
    const map = new Map<string, string>();
    if (market.data && data) for (const m of data.data) { const u = modelUrl(market.data.entries, m.id); if (u) map.set(m.id, u); }
    return map;
  }, [market.data, data]);
  const allProviders = ['All', ...Array.from(new Set(models.map((m) => displayName(m.owned_by))))];

  const filtered = models
    .filter((m) => provider === 'All' || displayName(m.owned_by) === provider)
    .filter((m) => {
      const q = search.toLowerCase();
      return !q || m.id.toLowerCase().includes(q) || displayName(m.owned_by).toLowerCase().includes(q);
    })
    .sort((a, b) => {
      const av = sortKey === 'id' ? a.id : displayName(a.owned_by);
      const bv = sortKey === 'id' ? b.id : displayName(b.owned_by);
      return sortAsc ? av.localeCompare(bv) : bv.localeCompare(av);
    });

  const toggleSort = (k: SortKey) => {
    if (sortKey === k) setSortAsc(!sortAsc);
    else { setSortKey(k); setSortAsc(true); }
  };

  const SortIcon = ({ k }: { k: SortKey }) => (
    <ArrowUpDown className={cn('w-3 h-3 inline-block ml-1 transition-colors', sortKey === k ? 'text-[var(--accent)]' : 'text-[var(--text-faint)]')} />
  );

  return (
    <DashPage
      title="Models"
      sub={`${models.length} models across ${allProviders.length - 1} providers`}
      actions={
        <button onClick={() => refetch()} className="h-9 px-4 rounded-lg flex items-center gap-2 text-[13px] font-medium text-[var(--text-secondary)] border border-[var(--border)] hover:bg-[var(--hover)] transition-colors">
          <RefreshCw className="w-3.5 h-3.5" /> Refresh
        </button>
      }
    >

          {isError && (
            <div className="card p-6 mt-6 text-center">
              <p className="text-sm font-medium text-white mb-1">Could not load the model registry</p>
              <p className="text-xs text-[var(--text-muted)] mb-4">Is the backend running? (expected at http://localhost:8000)</p>
              <button onClick={() => refetch()} className="h-9 px-4 rounded-lg text-[13px] font-medium text-black bg-[var(--accent)] hover:opacity-90 transition-opacity">
                Retry
              </button>
            </div>
          )}

          {!isError && (
            <>
              {/* Filters */}
              <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3 mt-6">
                <div className="flex items-center gap-2 h-8 px-3 rounded-lg border border-[var(--border)] bg-[var(--bg-card)] flex-1 max-w-sm">
                  <Search className="w-3.5 h-3.5 text-[var(--text-faint)]" />
                  <input
                    value={search} onChange={(e) => setSearch(e.target.value)}
                    placeholder="Search models..."
                    className="flex-1 bg-transparent text-[12px] text-[var(--text-primary)] outline-none placeholder:text-[var(--text-faint)]"
                  />
                </div>
                <div className="flex items-center gap-1 flex-wrap">
                  {allProviders.map((p) => (
                    <button
                      key={p}
                      onClick={() => setProvider(p)}
                      className={cn(
                        'h-7 px-2.5 rounded-md text-[11px] font-medium border transition-colors',
                        provider === p
                          ? 'bg-[var(--accent-dim)] border-[var(--accent)] text-[var(--accent)]'
                          : 'border-[var(--border)] text-[var(--text-muted)] hover:text-[var(--text-secondary)] hover:border-[var(--border-strong)]'
                      )}
                    >
                      {p}
                    </button>
                  ))}
                </div>
              </div>

              {/* Table */}
              <div className="mt-4">
                <ChartCard title="Model registry" legend={[{ color: 'var(--accent)', label: `${filtered.length} models` }]}>
                  <div className="overflow-x-auto">
                    <table className="text-[12px] w-full">
                      <thead>
                        <tr className="text-left text-[10px] uppercase tracking-widest text-[var(--text-faint)] border-b border-[var(--border)]">
                          {[
                            { k: 'id' as SortKey, label: 'Model' },
                            { k: 'provider' as SortKey, label: 'Provider' },
                            { k: null, label: 'Served by' },
                          ].map(({ k, label }) => (
                            <th
                              key={label}
                              onClick={() => k && toggleSort(k)}
                              className={cn(
                                'px-4 py-2.5 font-medium',
                                k && 'cursor-pointer hover:text-[var(--text-secondary)] select-none'
                              )}
                            >
                              {label}{k && <SortIcon k={k} />}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {isLoading && (
                          <tr><td colSpan={3} className="px-4 py-8 text-center text-[12px] text-[var(--text-faint)]">Loading…</td></tr>
                        )}
                        {!isLoading && filtered.map((m) => {
                        const url = urls.get(m.id);
                        return (
                          <tr key={m.id} className="border-b border-[var(--border)] last:border-0 hover:bg-[rgba(255,255,255,0.02)] transition-colors">
                            <td className="px-4 py-2.5 font-medium text-[var(--text-primary)]">
                              <div className="flex items-center gap-2">
                                {logoSlug[m.owned_by] && brandLogo[logoSlug[m.owned_by]] ? (
                                  <img
                                    src={brandLogo[logoSlug[m.owned_by]]}
                                    alt={`${m.owned_by} logo`}
                                    loading="lazy"
                                    className={wideLogo.has(logoSlug[m.owned_by])
                                      ? `h-[10px] w-auto max-w-[36px] object-contain shrink-0${filteredLogo.has(logoSlug[m.owned_by]) ? ' logo-white' : ''}`
                                      : 'w-3 h-3 object-contain shrink-0'}
                                  />
                                ) : (
                                  <Cpu className="w-3 h-3 shrink-0" style={{ color: displayColor(m.owned_by) }} />
                                )}
                                {url ? (
                                  <a
                                    href={url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    title={`Open ${m.id}`}
                                    className="font-mono text-[11px] inline-flex items-center gap-1 hover:text-[var(--accent)] underline-offset-2 hover:underline"
                                  >
                                    {m.id}
                                    <ExternalLink className="w-2.5 h-2.5 text-[var(--text-faint)] shrink-0" />
                                  </a>
                                ) : (
                                  <span className="font-mono text-[11px]">{m.id}</span>
                                )}
                              </div>
                            </td>
                            <td className="px-4 py-2.5">
                              <span className="inline-flex items-center gap-1.5">
                                <span className="w-1.5 h-1.5 rounded-full" style={{ background: displayColor(m.owned_by) }} />
                                <span className="text-[var(--text-secondary)]">{displayName(m.owned_by)}</span>
                              </span>
                            </td>
                            <td className="px-4 py-2.5 text-[var(--text-muted)] text-[11px]">
                              {m.providers.map((p, i) => (
                                <span key={p}>
                                  {i > 0 && ', '}
                                  <a href={providerUrl(p, market.data)} target="_blank" rel="noopener noreferrer" className="underline-offset-2 hover:text-[var(--accent)] hover:underline" title={`Open ${p}`}>{p}</a>
                                </span>
                              ))}
                            </td>
                          </tr>
                        );
                      })}
                        {!isLoading && !isError && filtered.length === 0 && (
                          <tr><td colSpan={3} className="px-4 py-8 text-center text-[12px] text-[var(--text-faint)]">
                            {models.length === 0 ? 'No models yet — connect a provider API key in Settings' : 'No models match your search.'}
                          </td></tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </ChartCard>
              </div>
            </>
          )}
    </DashPage>
  );
}
