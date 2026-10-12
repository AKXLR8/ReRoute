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

export function CostChart({ rows, action, title = 'Spend by provider' }: { rows: Analytics[]; action?: React.ReactNode; title?: string }) {
  const data = rows.map((r) => ({ name: displayName(r.provider), cost: r.total_cost_usd, color: displayColor(r.provider) }));
  const legend = rows.map((r) => ({ color: displayColor(r.provider), label: displayName(r.provider) }));
  return (
    <ChartCard title={title} action={action} legend={legend}>
      <ResponsiveContainer width="100%" height={220}>
        <AreaChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
          <XAxis dataKey="name" tick={{ fill: '#4B5563', fontSize: 10 }} axisLine={false} tickLine={false} />
          <YAxis tick={{ fill: '#4B5563', fontSize: 10 }} axisLine={false} tickLine={false} />
          <Tooltip {...tipStyle} formatter={(v) => [`$${Number(v ?? 0).toLocaleString(undefined, { maximumFractionDigits: 4 })}`, 'Cost']} />
          <Area type="monotone" dataKey="cost" name="Cost" stroke="#4493f8" strokeWidth={1.5} fill="rgba(68,147,248,0.1)" dot={false} />
        </AreaChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}
