import { ExternalLink } from 'lucide-react';
import { ChartCard } from './ChartCard';
import { fmtUsd, isFree, type NewestModel } from '../../lib/pricing';

/* ponytail: stdlib Date, no dep */
const dateFmt = (t: number) =>
  new Date(t * 1000).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });

export function NewestModels({ items, loading }: { items: NewestModel[]; loading?: boolean }) {
  return (
    <ChartCard title="Latest models" legend={[{ color: 'var(--blue)', label: 'OpenRouter · refreshed daily' }]}>
      {loading ? (
        <div className="px-2 pb-2 space-y-2 pt-2">
          {[0, 1, 2, 3, 4, 5].map((i) => <div key={i} className="skeleton h-[38px] rounded-md" />)}
        </div>
      ) : (
        <div className="px-2 pb-2">
          {items.map((m) => (
            <a
              key={m.id}
              href={`https://openrouter.ai/${m.id}`}
              target="_blank"
              rel="noopener noreferrer"
              title={`Open ${m.name} on OpenRouter`}
              className="block py-2.5 px-1 -mx-1 border-b border-[var(--border)] last:border-0 hover:bg-[var(--hover)] rounded-md transition-colors"
            >
              <div className="flex items-baseline justify-between gap-3">
                <p className="text-[12px] font-medium text-[var(--text-primary)] truncate flex items-center gap-1.5">
                  {m.name}
                  <ExternalLink className="w-3 h-3 text-[var(--text-faint)] shrink-0" />
                </p>
                <p className="text-[11px] tabular-nums text-[var(--text-muted)] shrink-0">
                  {dateFmt(m.created)} ·{' '}
                  {isFree(m) ? (
                    <span className="text-[var(--accent)] font-medium">Free</span>
                  ) : (
                    `${fmtUsd(m.inPerM)} in · ${fmtUsd(m.outPerM)} out`
                  )}
                </p>
              </div>
              <p className="text-[11px] text-[var(--text-faint)] truncate mt-0.5 font-mono">
                {m.id}{m.context > 0 && ` · ${Math.round(m.context / 1000)}k ctx`}
              </p>
            </a>
          ))}
          {items.length === 0 && (
            <p className="text-[12px] text-[var(--text-muted)] text-center py-8">Feed unreachable — check your network and refresh.</p>
          )}
        </div>
      )}
    </ChartCard>
  );
}
