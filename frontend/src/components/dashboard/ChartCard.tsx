import type { ReactNode } from 'react';

interface ChartCardProps {
  title: string;
  subtitle?: string;
  legend?: { color: string; label: string }[];
  empty?: boolean;
  emptyHint?: string;
  action?: ReactNode;
  children: ReactNode;
}

export function ChartCard({ title, subtitle, legend, empty, emptyHint, action, children }: ChartCardProps) {
  return (
    <div className="card p-0 overflow-hidden">
      <div className="flex items-center justify-between gap-3 px-5 pt-4 pb-2">
        <div className="min-w-0">
          <h3 className="text-[15px] font-bold text-[var(--text-primary)] truncate">{title}</h3>
          {subtitle && <p className="text-[11px] text-[var(--text-muted)] truncate mt-0.5">{subtitle}</p>}
        </div>
        {action}
      </div>

      {empty ? (
        <div className="flex flex-col items-center justify-center h-[220px] px-6 text-center">
          <p className="text-[13px] text-[var(--text-muted)]">{emptyHint ?? 'No data in this window'}</p>
        </div>
      ) : (
        <div className="px-3 pb-1">{children}</div>
      )}

      {legend && legend.length > 0 && (
        <div className="flex items-center gap-4 px-5 py-3 border-t border-[var(--border)]">
          {legend.map((item) => (
            <span key={item.label} className="flex items-center gap-1.5 text-[11px] text-[var(--text-muted)]">
              <span className="w-2 h-2 rounded-full shrink-0" style={{ background: item.color }} />
              {item.label}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
