import { useEffect, useMemo, useState } from 'react';
import { Check, ChevronDown, ChevronUp, ExternalLink, Search, X } from 'lucide-react';
import { providerDisplay } from '../../lib/api';
import { entryUrl, fmtUsd, isFree, prettyProvider, pricesFor, providerUrl, registryName, type MarketData, type PriceEntry } from '../../lib/pricing';

type SortKey = 'label' | 'in' | 'out' | 'ctx';

interface Row {
  label: string;
  price: PriceEntry;
  url: string | null;
  context?: number;
  tags?: string[];
}

export function PriceCompareModal({ model, entries, data, connected, onClose }: {
  model: string;
  entries: PriceEntry[];
  data?: MarketData | null;
  connected: Set<string>;
  onClose: () => void;
}) {
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState(model);
  const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 }>({ key: 'in', dir: 1 });

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const candidates = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return [];
    const uniq = Array.from(new Set(entries.map((e) => e.model)));
    const hits = uniq.filter((m) => m.toLowerCase().includes(q));
    hits.sort((a, b) =>
      (Number(b.toLowerCase().startsWith(q)) - Number(a.toLowerCase().startsWith(q))) ||
      a.localeCompare(b));
    return hits.slice(0, 30);
  }, [entries, query]);

  /* one row per displayed provider: cheapest price, first-seen capability/context,
     and a link from whichever twin in the group has one */
  const rows: Row[] = useMemo(() => {
    const groups = new Map<string, PriceEntry[]>();
    for (const e of pricesFor(entries, selected)) {
      const label = providerDisplay[registryName(e.provider)] ?? prettyProvider(e.provider);
      const g = groups.get(label);
      if (g) g.push(e);
      else groups.set(label, [e]);
    }
    const out: Row[] = [];
    for (const [label, g] of groups) {
      const price = g.reduce((a, b) => (b.inPerM < a.inPerM ? b : a));
      out.push({
        label,
        price,
        url: g.map(entryUrl).find((u) => u !== null) ?? providerUrl(price.provider, data),
        context: price.context ?? g.find((e) => e.context != null)?.context,
        tags: price.tags?.length ? price.tags : g.find((e) => e.tags?.length)?.tags,
      });
    }
    return out;
  }, [entries, selected, data]);

  const minIn = rows.length ? Math.min(...rows.map((r) => r.price.inPerM)) : 0;
  const minCount = rows.filter((r) => r.price.inPerM === minIn).length;

  const sorted = useMemo(() => {
    const copy = [...rows];
    copy.sort((a, b) => {
      const d =
        sort.key === 'label' ? a.label.localeCompare(b.label)
        : sort.key === 'in' ? a.price.inPerM - b.price.inPerM
        : sort.key === 'out' ? a.price.outPerM - b.price.outPerM
        : (a.context ?? -1) - (b.context ?? -1);
      return d * sort.dir;
    });
    return copy;
  }, [rows, sort]);

  const toggle = (key: SortKey) => setSort((s) => ({ key, dir: s.key === key && s.dir === 1 ? -1 : 1 }));
  const openRow = (r: Row) => { if (r.url) window.open(r.url, '_blank', 'noopener'); };
  const orRow = rows.find((r) => r.price.provider === 'openrouter');
  const fmtCtx = (c?: number) => (c ? `${Math.round(c / 1000)}k` : '—');

  const Th = ({ k, children, right }: { k: SortKey; children: React.ReactNode; right?: boolean }) => (
    <th className={`px-2 py-2 font-medium ${right ? 'text-right' : 'text-left'}`}>
      <button
        onClick={() => toggle(k)}
        className={`inline-flex items-center gap-1 uppercase tracking-wider hover:text-[var(--text-secondary)] transition-colors ${sort.key === k ? 'text-[var(--accent)]' : ''}`}
      >
        {children}
        {sort.key === k && (sort.dir === 1 ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />)}
      </button>
    </th>
  );

  return (
    <div className="fixed inset-0 z-[90] flex items-center justify-center bg-black/60 p-4" onClick={onClose}>
      <div
        className="w-full max-w-3xl max-h-[85vh] flex flex-col rounded-2xl shadow-2xl overflow-hidden"
        style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between gap-3 px-5 py-4 border-b border-[var(--border)]">
          <div className="min-w-0 flex items-center gap-2">
            <div className="min-w-0">
              <h3 className="text-[15px] font-semibold text-[var(--text-primary)]">Compare prices</h3>
              <p className="text-[11px] text-[var(--text-muted)] font-mono truncate">{selected}</p>
            </div>
            {orRow?.url && (
              <a
                href={orRow.url} target="_blank" rel="noopener noreferrer"
                title="Open this model on OpenRouter"
                className="w-8 h-8 rounded-lg flex items-center justify-center text-[var(--text-muted)] hover:text-[var(--accent)] hover:bg-[var(--hover)] transition-colors shrink-0"
              >
                <ExternalLink className="w-4 h-4" />
              </a>
            )}
          </div>
          <button onClick={onClose} aria-label="Close" className="w-8 h-8 rounded-lg flex items-center justify-center text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--hover)] transition-colors shrink-0">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Search any model in the feeds */}
        <div className="px-5 pt-4 relative">
          <div className="flex items-center gap-2 h-9 px-3 rounded-lg border border-[var(--border)] bg-black">
            <Search className="w-3.5 h-3.5 text-[var(--text-faint)] shrink-0" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search any model — gpt-5, llama-4, claude…"
              className="flex-1 bg-transparent text-[12px] text-[var(--text-primary)] outline-none placeholder:text-[var(--text-faint)]"
            />
          </div>
          {candidates.length > 0 && (
            <div className="absolute left-5 right-5 z-10 mt-1 max-h-44 overflow-y-auto rounded-lg border border-[var(--border)] shadow-lg" style={{ background: 'var(--bg-base)' }}>
              {candidates.map((m) => (
                <button
                  key={m}
                  onClick={() => { setSelected(m); setQuery(''); setSort({ key: 'in', dir: 1 }); }}
                  className={`w-full text-left px-3 py-2 text-[12px] font-mono hover:bg-[var(--hover)] transition-colors ${m === selected ? 'text-[var(--accent)]' : 'text-[var(--text-secondary)]'}`}
                >
                  {m}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Price rows */}
        <div className="px-5 py-4 overflow-y-auto overflow-x-auto sidebar-scroll">
          {rows.length === 0 ? (
            <p className="text-[13px] text-[var(--text-muted)] text-center py-8">
              No public price list yet for this model.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-[12px] min-w-[640px]">
                <thead>
                  <tr className="text-left text-[10px] uppercase tracking-widest text-[var(--text-faint)] border-b border-[var(--border)]">
                    <Th k="label">Provider</Th>
                    <Th k="in" right>Input /1M</Th>
                    <Th k="out" right>Output /1M</Th>
                    <Th k="ctx" right>Context</Th>
                    <th className="px-2 py-2 font-medium text-right">vs lowest</th>
                    <th className="px-2 py-2 font-medium text-right w-8" />
                  </tr>
                </thead>
                <tbody>
                  {sorted.map((r) => {
                    const lowest = r.price.inPerM === minIn;
                    const delta = r.price.inPerM - minIn;
                    return (
                      <tr
                        key={r.label}
                        onClick={() => openRow(r)}
                        title={r.url ? `Open at ${r.label}` : undefined}
                        className={`border-b border-[var(--border)] last:border-0 transition-colors ${r.url ? 'cursor-pointer' : ''} ${lowest ? 'bg-[var(--accent-dim)]' : 'hover:bg-[var(--hover)]'}`}
                      >
                        <td className="px-2 py-2.5">
                          <span className="flex items-center gap-2 text-[var(--text-primary)] font-medium">
                            <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: lowest ? 'var(--accent)' : 'var(--text-faint)' }} />
                            {r.label}
                            {connected.has(registryName(r.price.provider)) && (
                              <span className="inline-flex items-center gap-1 text-[10px] font-medium text-[var(--accent)]" title="Your connected key routes here">
                                <Check className="w-3 h-3" /> your key
                              </span>
                            )}
                          </span>
                          <p className="text-[10px] text-[var(--text-faint)] font-mono truncate mt-0.5 pl-3.5" title={r.price.model}>
                            {r.price.model}
                            {r.tags?.length ? ` · ${r.tags.join(' · ')}` : ''}
                          </p>
                        </td>
                        <td className="px-2 py-2.5 text-right tabular-nums text-[var(--text-secondary)]">
                          {isFree(r.price) ? <span className="text-[var(--accent)]">Free</span> : fmtUsd(r.price.inPerM)}
                        </td>
                        <td className="px-2 py-2.5 text-right tabular-nums text-[var(--text-secondary)]">
                          {isFree(r.price) ? <span className="text-[var(--accent)]">Free</span> : fmtUsd(r.price.outPerM)}
                        </td>
                        <td className="px-2 py-2.5 text-right tabular-nums text-[var(--text-muted)]">{fmtCtx(r.context)}</td>
                        <td className="px-2 py-2.5 text-right tabular-nums text-[11px]">
                          {delta === 0 ? (
                            <span className="text-[var(--accent)] font-medium">{minCount > 1 ? 'tie' : 'best'}</span>
                          ) : (
                            <span className="text-[var(--text-faint)]">+{fmtUsd(delta)}</span>
                          )}
                        </td>
                        <td className="px-2 py-2.5 text-right">
                          {r.url && <ExternalLink className="w-3.5 h-3.5 inline-block text-[var(--text-faint)]" />}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="px-5 py-3 border-t border-[var(--border)] text-[11px] text-[var(--text-faint)]">
          List prices per 1M tokens · click a row to open its pricing page · LiteLLM + OpenRouter · refreshed daily
        </div>
      </div>
    </div>
  );
}
