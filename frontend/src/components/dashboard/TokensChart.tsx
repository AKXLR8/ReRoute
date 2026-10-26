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

export function TokensChart({ days, rows }: { days: number; rows: ActivityDay[] }) {
  const byDate = new Map(rows.map((r) => [r.date, r]));
  const data = [];
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date();
    d.setDate(d.getDate() - i);
    const r = byDate.get(d.toISOString().slice(0, 10));
    data.push({
      name: d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
      Prompt: r?.input_tokens ?? 0,
      Completion: r?.output_tokens ?? 0,
    });
  }
  return (
    <ChartCard
      title="Token breakdown"
      legend={[
        { color: '#8B5CF6', label: 'Completion' },
        { color: '#4F8EF7', label: 'Prompt' },
      ]}
    >
      <ResponsiveContainer width="100%" height={220}>
        <AreaChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
          <XAxis dataKey="name" tick={{ fill: '#4B5563', fontSize: 10 }} axisLine={false} tickLine={false} interval="preserveStartEnd" />
          <YAxis tick={{ fill: '#4B5563', fontSize: 10 }} axisLine={false} tickLine={false} />
          <Tooltip {...tipStyle} formatter={(v, name) => [Number(v ?? 0).toLocaleString(), name]} />
          <Area type="monotone" dataKey="Prompt" stackId="t" stroke="#4F8EF7" strokeWidth={1.5} fill="rgba(79,142,247,0.12)" dot={{ r: 2.5 }} />
          <Area type="monotone" dataKey="Completion" stackId="t" stroke="#8B5CF6" strokeWidth={1.5} fill="rgba(139,92,246,0.15)" dot={{ r: 2.5 }} />
        </AreaChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}
