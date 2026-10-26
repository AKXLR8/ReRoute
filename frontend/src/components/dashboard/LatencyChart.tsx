import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
import { type Analytics, displayName, displayColor } from '../../lib/api';
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

export function LatencyChart({ rows }: { rows: Analytics[] }) {
  const data = rows.map((r) => ({ name: displayName(r.provider), latency: Math.round(r.avg_latency_ms) }));
  return (
    <ChartCard
      title="Latency by provider"
      legend={rows.map((r) => ({ color: displayColor(r.provider), label: displayName(r.provider) }))}
    >
      <ResponsiveContainer width="100%" height={220}>
        <AreaChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
          <defs>
            <linearGradient id="gLatency" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#F5B301" stopOpacity={0.2} />
              <stop offset="100%" stopColor="#F5B301" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
          <XAxis dataKey="name" tick={{ fill: '#4B5563', fontSize: 10 }} axisLine={false} tickLine={false} />
          <YAxis tick={{ fill: '#4B5563', fontSize: 10 }} axisLine={false} tickLine={false} />
          <Tooltip {...tipStyle} formatter={(v) => [`${Number(v ?? 0)}ms`, 'Latency']} />
          <Area type="monotone" dataKey="latency" name="Latency" stroke="#F5B301" strokeWidth={1.5} fill="url(#gLatency)" dot={{ r: 2.5 }} />
        </AreaChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}
