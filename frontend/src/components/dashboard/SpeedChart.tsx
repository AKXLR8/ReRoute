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

export function SpeedChart({ days, rows }: { days: number; rows: ActivityDay[] }) {
  const byDate = new Map(rows.map((r) => [r.date, r]));
  const data = [];
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date();
    d.setDate(d.getDate() - i);
    const r = byDate.get(d.toISOString().slice(0, 10));
    data.push({
      name: d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
      TTFT: r?.avg_ttft_ms != null ? Math.round(r.avg_ttft_ms) : null,
      'Tok/s': r?.avg_tokens_per_sec != null ? Math.round(r.avg_tokens_per_sec) : null,
    });
  }
  return (
    <ChartCard
      title="Streaming speed"
      legend={[
        { color: '#F5B301', label: 'TTFT (ms)' },
        { color: '#3B82F6', label: 'Tokens/sec' },
      ]}
    >
      <ResponsiveContainer width="100%" height={220}>
        <AreaChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
          <XAxis dataKey="name" tick={{ fill: '#4B5563', fontSize: 10 }} axisLine={false} tickLine={false} interval="preserveStartEnd" />
          <YAxis tick={{ fill: '#4B5563', fontSize: 10 }} axisLine={false} tickLine={false} />
          <Tooltip {...tipStyle} formatter={(v, name) => [Number(v ?? 0).toLocaleString(), name]} />
          <Area type="monotone" dataKey="TTFT" stroke="#F5B301" strokeWidth={1.5} fill="rgba(245,179,1,0.12)" dot={{ r: 2.5 }} connectNulls />
          <Area type="monotone" dataKey="Tok/s" stroke="#3B82F6" strokeWidth={1.5} fill="rgba(59,130,246,0.12)" dot={{ r: 2.5 }} connectNulls />
        </AreaChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}
