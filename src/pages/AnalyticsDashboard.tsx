import { useEffect, useMemo, useState, type CSSProperties, type ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Cell, Pie, PieChart, ResponsiveContainer } from 'recharts';
import { KeyRound, RefreshCw, Wifi } from 'lucide-react';
import { api, displayName, displayColor, providerDisplay, type AuditLog } from '../lib/api';
import { signOut } from '../lib/nav';
import { DashPage, Segmented } from '../components/dashboard/DashPage';
import { ActivityChart } from '../components/dashboard/ActivityChart';
import { CostChart } from '../components/dashboard/CostChart';
import { TokensChart } from '../components/dashboard/TokensChart';
import { CachingChart } from '../components/dashboard/CachingChart';
import { SpeedChart } from '../components/dashboard/SpeedChart';
import { TopList, type TopItem } from '../components/dashboard/TopList';
import { NewestModels } from '../components/dashboard/NewestModels';
import { PriceCompareModal } from '../components/dashboard/PriceCompareModal';
import { ErrorBoundary } from '../components/dashboard/ErrorBoundary';
import { cheapestByProvider, entryUrl, fetchMarket, fmtUsd, isFree, modelUrl, pricesFor, providerUrl, registryName } from '../lib/pricing';

const DARK_FACE = {
  background: 'linear-gradient(160deg,#18181B 0%,#0B0B0C 100%)',
  border: '1px solid rgba(255,255,255,0.10)',
  boxShadow: '0 24px 48px rgba(0,0,0,0.55)',
};

const BRAND_FACE = { background: 'linear-gradient(135deg,#C7D2FE 0%,#A5B4FC 45%,#818CF8 100%)', boxShadow: '0 24px 48px rgba(0,0,0,0.45)' };

function CardShell({ face, children }: { face: CSSProperties; children: ReactNode }) {
  return (
    <div className="w-full h-full rounded-2xl p-5 flex flex-col overflow-hidden" style={face}>
      {children}
    </div>
  );
}

function CardBrandRow({ invert }: { invert?: boolean }) {
  return (
    <div className="flex items-start justify-between">
      <div className="flex items-center gap-2">
        <img src="/logo.png" alt="" className="h-18 w-auto object-contain" style={invert ? { filter: 'brightness(0) invert(1)' } : undefined} />
        <span className="text-[13px] font-medium text-white">ReRouteAI.</span>
      </div>
      <Wifi className="w-5 h-5 text-white/60 -rotate-90" />
    </div>
  );
}

function CardMeta({ label, right, line, foot }: { label: string; right: string; line: string; foot: string }) {
  return (
    <div className="mt-auto">
      <div className="flex items-center justify-between mb-2">
        <span className="text-[11px] uppercase tracking-wider text-white/45">{label}</span>
        <span className="text-[11px] text-white/45 font-mono">{right}</span>
      </div>
      <p className="text-[12px] sm:text-[16px] font-mono tracking-[0.12em] sm:tracking-[0.16em] text-white truncate">{line}</p>
      <div className="flex items-center justify-between mt-3">
        <span className="text-[12px] text-white/60">{foot}</span>
        <span className="w-8 h-5 rounded-full bg-white/15 relative shrink-0"><span className="absolute right-0.5 top-0.5 w-4 h-4 rounded-full bg-white/90" /></span>
      </div>
    </div>
  );
}

/* three faces of the deck: prod key, routing, brand */
const DECK = [
  {
    id: 'prod',
    node: (
      <CardShell face={DARK_FACE}>
        <CardBrandRow invert />
        <CardMeta label="gateway · prod" right="v0.1" line="sk-prod •••• •••• ••••" foot="40+ providers · 1 endpoint" />
      </CardShell>
    ),
  },
  {
    id: 'routing',
    node: (
      <CardShell face={DARK_FACE}>
        <CardBrandRow invert />
        <CardMeta label="gateway · routing" right="v0.1" line="OpenAI-compatible" foot="routing · caching · failover" />
      </CardShell>
    ),
  },
  {
    id: 'brand',
    node: (
      <CardShell face={BRAND_FACE}>
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-2">
            <img src="/logo.png" alt="" className="h-18 w-auto object-contain" />
            <span className="text-[13px] font-semibold text-[#1E1B4B]">ReRouteAI.</span>
          </div>
          <Wifi className="w-5 h-5 text-[#1E1B4B]/50 -rotate-90" />
        </div>
        <div className="mt-auto flex items-center justify-between">
          <span className="text-[11px] uppercase tracking-wider text-[#1E1B4B]/60">gateway · brand</span>
          <span className="w-8 h-5 rounded-full bg-black/15 relative shrink-0"><span className="absolute right-0.5 top-0.5 w-4 h-4 rounded-full bg-white/90" /></span>
        </div>
      </CardShell>
    ),
  },
];

/* slot geometry: front, mid, back. every offset stays inside the 236px box,
   so the deck never crosses into the Recent list below it */
const SLOTS = [
  { x: 0, y: 0, rotate: 0, scale: 1, zIndex: 30 },
  { x: -13, y: 10, rotate: -3.5, scale: 0.965, zIndex: 20 },
  { x: -26, y: 20, rotate: -7, scale: 0.93, zIndex: 10 },
];

const EASE = [0.22, 1, 0.36, 1] as const;

function CardStack() {
  const [step, setStep] = useState(0);
  const [paused, setPaused] = useState(false);

  useEffect(() => {
    if (paused || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const t = setInterval(() => setStep((s) => s + 1), 3400);
    return () => clearInterval(t);
  }, [paused]);

  return (
    <div
      className="relative h-[236px] select-none"
      aria-hidden="true"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
    >
      {SLOTS.map((slot, i) => {
        const face = DECK[(step + i) % DECK.length];
        return (
          <motion.div
            key={face.id}
            className="absolute right-0 top-0 w-[86%] h-[200px]"
            style={{ zIndex: slot.zIndex }}
            initial={{ x: 0, y: 16, rotate: 0, scale: 1, opacity: 0 }}
            animate={{ x: slot.x, y: slot.y, rotate: slot.rotate, scale: slot.scale, opacity: 1 }}
            transition={{ duration: 0.65, ease: EASE, delay: i * 0.07 }}
          >
            {face.node}
          </motion.div>
        );
      })}
    </div>
  );
}

function RecentList({ logs }: { logs: AuditLog[] }) {
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <h3 className="text-[15px] font-bold text-[var(--text-primary)]">Recent requests</h3>
        <Link to="/dashboard/logs" className="text-[12px] text-[var(--text-muted)] hover:text-white transition-colors">View all</Link>
      </div>
      {logs.length === 0 && <p className="py-6 text-[13px] text-[var(--text-muted)]">No requests yet.</p>}
      {logs.slice(0, 8).map((l, i) => {
        const t = new Date(l.timestamp);
        const when = `${t.toLocaleDateString('en-US', { weekday: 'long' })} ${t.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })}`;
        return (
          <div key={l.id ?? i} className="flex items-center justify-between gap-3 py-3.5 border-t border-[var(--border)]">
            <div className="min-w-0">
              <p className="text-[14px] font-semibold text-[var(--text-primary)] truncate">{l.model_served}</p>
              <p className={`text-[13px] ${l.cost_usd === 0 && l.is_cached ? 'text-emerald-400' : 'text-[var(--text-muted)]'}`}>
                {l.is_cached
                  ? (l.cache_saved_usd > 0 ? `+ saved $${l.cache_saved_usd.toFixed(4)}` : '+ $0.00 cached')
                  : `- $${l.cost_usd.toFixed(4)}`}
              </p>
            </div>
            <div className="text-right shrink-0">
              <p className="text-[12px] text-[var(--text-muted)]">{when}</p>
              <p className="text-[11px] text-[var(--text-faint)]">
                {Math.round(l.latency_ms)}ms
                {l.ttft_ms != null && ` · ${Math.round(l.ttft_ms)}ms TTFT`}
              </p>
              {l.finish_reason === 'length' && (
                <p className="text-[10px] text-amber-400">truncated</p>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

const CONNECTABLE = new Set(Object.keys(providerDisplay));

export default function AnalyticsDashboard() {
  const [days, setDays] = useState(30);
  const [compare, setCompare] = useState<string | null>(null);

  const analytics = useQuery({ queryKey: ['analytics', days], queryFn: () => api.getAnalytics(days) });
  const activity = useQuery({ queryKey: ['activity', days], queryFn: () => api.getActivity(days) });
  const breakdown = useQuery({ queryKey: ['breakdown', days], queryFn: () => api.getBreakdown(days) });
  const logs = useQuery({ queryKey: ['logs'], queryFn: () => api.listLogs(15) });

  const market = useQuery({ queryKey: ['pricing'], queryFn: fetchMarket, staleTime: 24 * 60 * 60 * 1000, retry: 1 });
  const providerKeys = useQuery({ queryKey: ['providers'], queryFn: () => api.listProviders() });

  const rows = analytics.data ?? [];
  const actRows = activity.data ?? [];
  const totalCost = rows.reduce((s, r) => s + r.total_cost_usd, 0);
  const donut = rows.filter((r) => r.total_cost_usd > 0)
    .map((r) => ({ name: displayName(r.provider), value: r.total_cost_usd, color: displayColor(r.provider) }));

  const isLoading = analytics.isLoading || activity.isLoading || breakdown.isLoading || logs.isLoading;
  const err = analytics.error ?? activity.error ?? breakdown.error ?? logs.error;
  const isError = analytics.isError || activity.isError || breakdown.isError || logs.isError;
  const unauthorized = !!err && /401/.test(String(err));
  const refetchAll = () => { analytics.refetch(); activity.refetch(); breakdown.refetch(); logs.refetch(); };

  const feed = market.data?.entries;
  const connected = useMemo(() => new Set((providerKeys.data ?? []).map((p) => p.provider)), [providerKeys.data]);
  const cheapestBy = useMemo(() => (feed ? cheapestByProvider(feed) : null), [feed]);

  /* Cards rank your real traffic first; leftover slots fill with other
     connectable providers/models from the price feed (0 req) so the lists
     stay populated and comparable. */
  const providerItems = useMemo<TopItem[]>(() => {
    const used: TopItem[] = (breakdown.data?.by_provider ?? [])
      .filter((p) => !!p.name)
      .map((p) => {
        const c = cheapestBy?.get(p.name!);
        return {
          name: p.name ?? 'gateway',
          sub: p.name ? displayName(p.name) : undefined,
          requests: p.requests,
          cost_usd: p.cost_usd,
          price: c ? (isFree(c) ? `free model: ${c.model}` : `from ${fmtUsd(c.inPerM)}/1M · ${c.model}`) : undefined,
          url: p.name ? providerUrl(p.name, market.data) : undefined,
        };
      });
    if (!feed || !cheapestBy || used.length >= 5) return used;
    const seen = new Set(used.map((i) => i.name));
    const extra = [...cheapestBy.entries()]
      .filter(([p]) => CONNECTABLE.has(p) && !seen.has(p))
      .sort((a, b) => a[1].inPerM - b[1].inPerM)
      .map(([p, c]) => ({
        name: p,
        sub: displayName(p),
        requests: 0,
        cost_usd: 0,
        price: isFree(c) ? `free model: ${c.model}` : `from ${fmtUsd(c.inPerM)}/1M · ${c.model}`,
        url: providerUrl(p, market.data),
      }));
    return [...used, ...extra.slice(0, 5 - used.length)];
  }, [breakdown.data, feed, cheapestBy, market.data]);

  const modelItems = useMemo<TopItem[]>(() => {
    const used: TopItem[] = (breakdown.data?.by_model ?? [])
      .filter((m) => !!m.model)
      .map((m) => {
        const matches = feed ? pricesFor(feed, m.model ?? '') : [];
        const cheap = matches.length ? matches.reduce((a, b) => (b.inPerM < a.inPerM ? b : a)) : null;
        const or = matches.find((e) => e.provider === 'openrouter');
        const url = (or ? entryUrl(or) : matches.map(entryUrl).find((u) => u !== null)) ?? undefined;
        return {
          name: m.model ?? 'unknown',
          sub: m.avg_ttft_ms != null
            ? `${Math.round(m.avg_ttft_ms)}ms TTFT · ${Math.round(m.avg_latency_ms)}ms latency${m.truncated > 0 ? ` · ${m.truncated} truncated` : ''}`
            : `${Math.round(m.avg_latency_ms)}ms avg latency`,
          requests: m.requests,
          cost_usd: m.cost_usd,
          price: cheap ? (isFree(cheap) ? 'free to serve' : `from ${fmtUsd(cheap.inPerM)} in · ${fmtUsd(cheap.outPerM)} out /1M`) : undefined,
          compare: matches.length,
          onCompare: matches.length ? () => setCompare(m.model ?? '') : undefined,
          url,
        };
      });
    if (!feed || !cheapestBy || used.length >= 5) return used;
    const seen = new Set(used.map((i) => i.name));
    const extra = [...cheapestBy.values()]
      .filter((c) => CONNECTABLE.has(registryName(c.provider)) && !seen.has(c.model))
      .sort((a, b) => a.inPerM - b.inPerM)
      .map((c) => ({
        name: c.model,
        sub: displayName(registryName(c.provider)),
        requests: 0,
        cost_usd: 0,
        price: isFree(c) ? 'free to serve' : `from ${fmtUsd(c.inPerM)} in · ${fmtUsd(c.outPerM)} out /1M`,
        compare: pricesFor(feed, c.model).length,
        onCompare: () => setCompare(c.model),
        url: modelUrl(feed, c.model) ?? undefined,
      }));
    return [...used, ...extra.slice(0, 5 - used.length)];
  }, [breakdown.data, feed, cheapestBy]);

  return (
    <DashPage
      title="Your gateway"
      sub="Welcome back — here's your spend."
      actions={
        <>
          <button onClick={refetchAll} className="h-9 px-4 rounded-lg flex items-center gap-2 text-[13px] font-medium text-[var(--text-secondary)] border border-[var(--border)] hover:bg-[var(--hover)] transition-colors">
            <RefreshCw className="w-3.5 h-3.5" /> Refresh
          </button>
          <Link to="/dashboard/settings?add=1" className="h-9 px-4 rounded-lg flex items-center gap-2 text-[13px] font-medium text-white transition-opacity hover:opacity-90" style={{ background: 'var(--purple)' }}>
            <KeyRound className="w-3.5 h-3.5" /> Add your key
          </Link>
        </>
      }
    >
        {isError && (
          <div className="card p-6 mb-6 text-center">
            <p className="text-sm font-medium text-white mb-1">
              {unauthorized ? 'Session expired' : 'Could not load analytics'}
            </p>
            <p className="text-xs text-[var(--text-muted)] mb-4">
              {unauthorized ? 'Your session expired — sign in again to reload your keys and spend.' : 'Could not reach the gateway API.'}
            </p>
            <div className="flex items-center justify-center gap-2">
              {!unauthorized && (
                <button onClick={refetchAll} className="h-9 px-4 rounded-lg text-[13px] font-medium text-black bg-[var(--accent)] hover:opacity-90 transition-opacity">Retry</button>
              )}
              <button onClick={signOut} className="h-9 px-4 rounded-lg text-[13px] font-medium text-[var(--text-muted)] border border-[var(--border)] hover:bg-[var(--hover)] hover:text-[var(--text-primary)] transition-colors">Sign out</button>
            </div>
          </div>
        )}

        {isLoading ? (
          <div className="grid grid-cols-1 lg:grid-cols-[360px_1fr] gap-6">
            <div className="space-y-4"><div className="skeleton h-[236px] rounded-2xl" /><div className="skeleton h-[320px] rounded-2xl" /></div>
            <div className="space-y-4"><div className="skeleton h-[320px] rounded-2xl" /><div className="skeleton h-[280px] rounded-2xl" /></div>
          </div>
        ) : (
          <ErrorBoundary>
            <div className="grid grid-cols-1 lg:grid-cols-[360px_1fr] gap-6 items-start">
              {/* LEFT: cards + recent */}
              <div>
                <CardStack />
                <div className="card p-5 mt-6">
                  <RecentList logs={logs.data ?? []} />
                </div>
              </div>

              {/* RIGHT: spending */}
              <div className="space-y-4">
                <div className="card p-5">
                  <div className="flex items-center justify-between gap-3 mb-4">
                    <h3 className="text-[15px] font-bold text-[var(--text-primary)]">Monthly spending</h3>
                    <Segmented value={days} onChange={setDays} />
                  </div>
                  <div className="flex flex-col sm:flex-row items-center gap-6">
                    <div className="relative w-[210px] h-[210px] shrink-0">
                      <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                          <Pie data={donut.length ? donut : [{ name: 'none', value: 1, color: '#1A1A1A' }]}
                            dataKey="value" nameKey="name" innerRadius={68} outerRadius={96} paddingAngle={3} stroke="none" startAngle={90} endAngle={-270}>
                            {(donut.length ? donut : [{ color: '#1A1A1A' }]).map((d, i) => <Cell key={i} fill={d.color} />)}
                          </Pie>
                        </PieChart>
                      </ResponsiveContainer>
                      <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                        <span className="text-[12px] text-[var(--text-muted)]">Total</span>
                        <span className="text-[26px] font-bold text-white tracking-tight">
                          {donut.length ? `$${totalCost.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : '$0'}
                        </span>
                      </div>
                    </div>
                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-x-6 gap-y-4 flex-1 w-full">
                      {donut.length === 0 && <p className="text-[13px] text-[var(--text-muted)] col-span-full">No spend in this window.</p>}
                      {donut.map((d) => (
                        <div key={d.name}>
                          <div className="flex items-center gap-1.5 mb-1">
                            <span className="w-2 h-2 rounded-full shrink-0" style={{ background: d.color }} />
                            <span className="text-[12px] text-[var(--text-muted)] truncate">{d.name}</span>
                          </div>
                          <p className="text-[17px] font-bold text-white tracking-tight">${d.value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                <ActivityChart days={days} rows={actRows} title="Balance over time" action={<Segmented value={days} onChange={setDays} />} />
                <CostChart rows={rows} action={<Segmented value={days} onChange={setDays} />} />

                <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
                  <TokensChart days={days} rows={actRows} />
                  <CachingChart days={days} rows={actRows} />
                  <SpeedChart days={days} rows={actRows} />
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
                  <TopList title="Top Providers" emptyHint="No traffic yet — send your first request through the gateway and providers will rank here." items={providerItems} />
                  <TopList title="Top Models" emptyHint="No traffic yet — models you serve will rank here by requests and spend." items={modelItems} />
                  <NewestModels loading={market.isLoading} items={(market.data?.newest ?? []).slice(0, 6)} />
                </div>
              </div>
            </div>
          </ErrorBoundary>
        )}

        {compare && market.data && (
          <PriceCompareModal model={compare} entries={market.data.entries} data={market.data} connected={connected} onClose={() => setCompare(null)} />
        )}
    </DashPage>
  );
}
