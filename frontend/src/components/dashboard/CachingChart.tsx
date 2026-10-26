import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
import { type ActivityDay } from '../../lib/api';
import { ChartCard } from './ChartCard';

const tipStyle = {
  contentStyle: {
    background: '#111111',
    border: '1px solid rgba(255,255,255,0.06)',
    borderRadius: 8,
    color: '#fff',
    fontSize: 12,
    padding: '6px 10px',
    boxShadow: '0 4px 16px rgba(0,0,0,0.5)',
  },
  itemStyle: { color: '#fff' },
  cursor: { stroke: 'rgba(255,255,255,0.08)', strokeWidth: 1 },
};

export function CachingChart({ days, rows }: { days: number; rows: ActivityDay[] }) {
  const byDate = new Map(rows.map((r) => [r.date, r]));
  const saved = rows.reduce((s, r) => s + (r.cache_saved_usd ?? 0), 0);
  const data = [];
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date();
    d.setDate(d.getDate() - i);
    const r = byDate.get(d.toISOString().slice(0, 10));
    const cached = r?.cached ?? 0;
    data.push({
      name: d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
      Cached: cached,
      Uncached: Math.max(0, (r?.requests ?? 0) - cached),
    });
  }
  return (
    <ChartCard
      title="Prompt token caching"
      subtitle={saved > 0 ? `saved $${saved.toFixed(4)} vs uncached` : undefined}
      legend={[
        { color: '#9CA3AF', label: 'Uncached' },
        { color: '#F5B301', label: 'Cached' },
      ]}
    >
      <ResponsiveContainer width="100%" height={220}>
        <AreaChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
          <XAxis dataKey="name" tick={{ fill: '#4B5563', fontSize: 10 }} axisLine={false} tickLine={false} interval="preserveStartEnd" />
          <YAxis tick={{ fill: '#4B5563', fontSize: 10 }} axisLine={false} tickLine={false} />
          <Tooltip {...tipStyle} formatter={(v, name) => [Number(v ?? 0).toLocaleString(), name]} />
          <Area type="monotone" dataKey="Uncached" stackId="c" stroke="#9CA3AF" strokeWidth={1.5} fill="rgba(156,163,175,0.12)" dot={{ r: 2.5 }} />
          <Area type="monotone" dataKey="Cached" stackId="c" stroke="#F5B301" strokeWidth={1.5} fill="rgba(245,179,1,0.15)" dot={{ r: 2.5 }} />
        </AreaChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}
