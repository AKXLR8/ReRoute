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

function fillDays(days: number, rows: ActivityDay[]) {
  const byDate = new Map(rows.map((r) => [r.date, r]));
  const out = [];
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date();
    d.setDate(d.getDate() - i);
    const key = d.toISOString().slice(0, 10);
    const r = byDate.get(key);
    out.push({
      name: d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
      requests: r?.requests ?? 0,
      cost: r ? Math.round(r.cost_usd * 100) / 100 : 0,
    });
  }
  return out;
}

export function ActivityChart({ days, rows, title = 'Usage by model', action }: { days: number; rows: ActivityDay[]; title?: string; action?: React.ReactNode }) {
  const data = fillDays(days, rows);
  return (
    <ChartCard
      title={title}
      action={action}
      legend={[
        { color: '#F5B301', label: 'Spend' },
        { color: '#00D2A0', label: 'Requests' },
      ]}
    >
      <ResponsiveContainer width="100%" height={220}>
        <AreaChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
          <defs>
            <linearGradient id="gReq" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#00D2A0" stopOpacity={0.2} />
              <stop offset="100%" stopColor="#00D2A0" stopOpacity={0} />
            </linearGradient>
            <linearGradient id="gCostAct" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#F5B301" stopOpacity={0.2} />
              <stop offset="100%" stopColor="#F5B301" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
          <XAxis dataKey="name" tick={{ fill: '#4B5563', fontSize: 10 }} axisLine={false} tickLine={false} interval="preserveStartEnd" />
          <YAxis yAxisId="req" tick={{ fill: '#4B5563', fontSize: 10 }} axisLine={false} tickLine={false} />
          <YAxis yAxisId="cost" orientation="right" tick={{ fill: '#4B5563', fontSize: 10 }} axisLine={false} tickLine={false} />
          <Tooltip {...tipStyle} formatter={(v, name) => [name === 'Spend' ? `$${Number(v ?? 0)}` : Number(v ?? 0).toLocaleString(), name]} />
          <Area yAxisId="req" type="monotone" dataKey="requests" name="Requests" stroke="#00D2A0" strokeWidth={1.5} fill="url(#gReq)" dot={{ r: 2.5 }} />
          <Area yAxisId="cost" type="monotone" dataKey="cost" name="Spend" stroke="#F5B301" strokeWidth={1.5} fill="url(#gCostAct)" dot={{ r: 2.5 }} />
        </AreaChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}
