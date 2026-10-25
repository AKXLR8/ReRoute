import { ExternalLink } from 'lucide-react';
import { ChartCard } from './ChartCard';

export interface TopItem {
  name: string;
  sub?: string;
  requests: number;
  cost_usd: number;
  price?: string;
  compare?: number;
  onCompare?: () => void;
  url?: string;
}

export function TopList({ title, items, emptyHint }: { title: string; items: TopItem[]; emptyHint?: string }) {
  const max = Math.max(1, ...items.map((i) => i.cost_usd));
  return (
    <ChartCard title={title} empty={items.length === 0} emptyHint={emptyHint}>
      <div className="px-2 pb-2">
        {items.slice(0, 5).map((i) => (
          <div key={i.name} className="py-2.5 border-b border-[var(--border)] last:border-0">
            <div className="flex items-baseline justify-between gap-3">
              {i.url ? (
                <a
                  href={i.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  title={`Open ${i.name}`}
                  className="min-w-0 truncate text-[12px] font-mono text-[var(--text-primary)] hover:text-[var(--accent)] underline-offset-2 hover:underline inline-flex items-center gap-1.5"
                >
                  {i.name}
                  <ExternalLink className="w-3 h-3 text-[var(--text-faint)] shrink-0" />
                </a>
              ) : (
                <p className="min-w-0 truncate text-[12px] font-mono text-[var(--text-primary)]">{i.name}</p>
              )}
              <p className="text-[11px] tabular-nums text-[var(--text-muted)] shrink-0">
                {i.requests.toLocaleString()} req · ${i.cost_usd.toFixed(4)}
              </p>
            </div>
            {i.sub && <p className="text-[11px] text-[var(--text-faint)] truncate mt-0.5">{i.sub}</p>}
            {i.price && (
              <div className="flex items-baseline justify-between gap-2 mt-1">
                <p className="text-[11px] tabular-nums text-[var(--text-muted)] truncate">{i.price}</p>
                {i.onCompare && i.compare ? (
                  <button
                    onClick={i.onCompare}
                    className="text-[11px] font-medium text-[var(--accent)] hover:underline shrink-0"
                  >
                    Compare {i.compare} →
                  </button>
                ) : null}
              </div>
            )}
            <div className="h-1 mt-1.5 rounded-full bg-[rgba(255,255,255,0.06)] overflow-hidden">
              <div className="h-full rounded-full bg-[var(--accent)]" style={{ width: `${(i.cost_usd / max) * 100}%` }} />
            </div>
          </div>
        ))}
      </div>
    </ChartCard>
  );
}
