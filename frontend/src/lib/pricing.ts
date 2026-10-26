/* Live market data — fetched in the background, cached 24h (the "daily scrape").
   Three CORS-open public feeds, no backend endpoint needed:
   - LiteLLM community table → direct-provider list prices (what BYOK actually pays)
   - OpenRouter /api/v1/models → newest models + market prices
   - OpenRouter /api/v1/providers → official provider slugs (grounded link targets)
   ponytail: no scraper service; the browser re-pulls all three on first use per day. */

export interface PriceEntry {
  model: string;
  provider: string; // litellm_provider slug or "openrouter"
  inPerM: number; // USD per 1M input tokens
  outPerM: number; // USD per 1M output tokens
  context?: number; // input context window in tokens
  source?: string; // provider docs/pricing URL, straight from the feed
  tags?: string[]; // capability chips: tools / vision / cache
}

export interface NewestModel {
  id: string;
  name: string;
  created: number; // unix seconds
  inPerM: number;
  outPerM: number;
  context: number;
}

export interface MarketData {
  entries: PriceEntry[];
  newest: NewestModel[];
  /* official OpenRouter providers, keyed by norm(name): {name, slug} */
  providers: Map<string, { name: string; slug: string }>;
}

const LITELLM_URL =
  'https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json';
const OPENROUTER_URL = 'https://openrouter.ai/api/v1/models';
const OR_PROVIDERS_URL = 'https://openrouter.ai/api/v1/providers';

const CHAT_MODES = new Set(['chat', 'responses', 'completion']);

const norm = (s: string) => s.toLowerCase().replace(/[^a-z0-9]/g, '');

async function fetchLiteLLM(): Promise<PriceEntry[]> {
  const res = await fetch(LITELLM_URL);
  if (!res.ok) throw new Error(`litellm feed HTTP ${res.status}`);
  const data = (await res.json()) as Record<string, Record<string, unknown>>;
  const out: PriceEntry[] = [];
  for (const [model, v] of Object.entries(data)) {
    if (v.mode !== undefined && !CHAT_MODES.has(String(v.mode))) continue;
    if (typeof v.input_cost_per_token !== 'number') continue;
    const context =
      typeof v.max_input_tokens === 'number'
        ? v.max_input_tokens
        : typeof v.max_tokens === 'number'
          ? v.max_tokens
          : undefined;
    out.push({
      model,
      provider: String(v.litellm_provider ?? ''),
      inPerM: v.input_cost_per_token * 1e6,
      outPerM: typeof v.output_cost_per_token === 'number' ? v.output_cost_per_token * 1e6 : 0,
      context,
      source: typeof v.source === 'string' && /^https:\/\//.test(v.source) ? v.source : undefined,
      tags: [
        v.supports_function_calling === true ? 'tools' : null,
        v.supports_vision === true ? 'vision' : null,
        v.supports_prompt_caching === true ? 'cache' : null,
      ].filter((t): t is string => t !== null),
    });
  }
  return out;
}

interface ORModel {
  id: string;
  name: string;
  created: number;
  context_length?: number;
  pricing?: { prompt?: string; completion?: string };
  supported_parameters?: string[];
  architecture?: { input_modalities?: string[] };
}

async function fetchOpenRouter(): Promise<{ entries: PriceEntry[]; newest: NewestModel[] }> {
  const res = await fetch(OPENROUTER_URL);
  if (!res.ok) throw new Error(`openrouter HTTP ${res.status}`);
  const data = (await res.json()) as { data: ORModel[] };
  const entries: PriceEntry[] = [];
  const newest: NewestModel[] = [];
  const seenBase = new Set<string>();
  for (const m of data.data) {
    if (!m.id || typeof m.created !== 'number') continue;
    const inPerM = Number(m.pricing?.prompt ?? 0) * 1e6;
    const outPerM = Number(m.pricing?.completion ?? 0) * 1e6;
    const tags = [
      (m.supported_parameters ?? []).includes('tools') ? 'tools' : null,
      (m.architecture?.input_modalities ?? []).includes('image') ? 'vision' : null,
    ].filter((t): t is string => t !== null);
    entries.push({ model: m.id, provider: 'openrouter', inPerM, outPerM, context: m.context_length, tags });
    if (/:batch$/.test(m.id)) continue; // batch mirrors are not "new models"
    const base = m.id.replace(/:(free|weekly)$/, '');
    if (seenBase.has(base)) continue;
    seenBase.add(base);
    newest.push({
      id: m.id,
      name: m.name || m.id,
      created: m.created,
      inPerM,
      outPerM,
      context: m.context_length ?? 0,
    });
  }
  newest.sort((a, b) => b.created - a.created);
  return { entries, newest };
}

async function fetchOrProviders(): Promise<Map<string, { name: string; slug: string }>> {
  const res = await fetch(OR_PROVIDERS_URL);
  if (!res.ok) throw new Error(`providers feed HTTP ${res.status}`);
  const json = (await res.json()) as { data?: { name?: string; slug?: string }[] };
  const map = new Map<string, { name: string; slug: string }>();
  for (const p of json.data ?? []) {
    if (p.name && p.slug) map.set(norm(p.name), { name: p.name, slug: p.slug });
  }
  return map;
}

const MARKET_KEY = 'market_cache_v1';
const MARKET_TTL = 24 * 60 * 60 * 1000;

interface StoredMarket {
  at: number;
  entries: PriceEntry[];
  newest: NewestModel[];
  providers: [string, { name: string; slug: string }][];
}

export async function fetchMarket(): Promise<MarketData> {
  // ponytail: localStorage, not a service — a reload shouldn't re-pull 3 MB of
  // feeds and re-parse them on the main thread.
  try {
    const raw = localStorage.getItem(MARKET_KEY);
    if (raw) {
      const c = JSON.parse(raw) as StoredMarket;
      if (Date.now() - c.at < MARKET_TTL) {
        return { entries: c.entries, newest: c.newest, providers: new Map(c.providers) };
      }
    }
  } catch {
    // corrupt or full storage → fall through to a fresh fetch
  }

  const [lite, or, prov] = await Promise.allSettled([fetchLiteLLM(), fetchOpenRouter(), fetchOrProviders()]);
  if (lite.status === 'rejected' && or.status === 'rejected') throw lite.reason;
  const entries = [
    ...(lite.status === 'fulfilled' ? lite.value : []),
    ...(or.status === 'fulfilled' ? or.value.entries : []),
  ];
  const data: MarketData = {
    entries,
    newest: or.status === 'fulfilled' ? or.value.newest : [],
    providers: prov.status === 'fulfilled' ? prov.value : new Map(),
  };
  try {
    localStorage.setItem(
      MARKET_KEY,
      JSON.stringify({ at: Date.now(), entries: data.entries, newest: data.newest, providers: [...data.providers] }),
    );
  } catch {
    // quota exceeded → still return this fetch's data
  }
  return data;
}

/* Match a gateway model id against feed keys (many are provider-prefixed). */
export function pricesFor(entries: PriceEntry[], modelId: string): PriceEntry[] {
  const n = norm(modelId);
  if (!n) return [];
  return entries.filter((e) => {
    const m = norm(e.model);
    const bare = e.model.includes('/') ? norm(e.model.slice(e.model.lastIndexOf('/') + 1)) : m;
    if (m === n || bare === n) return true;
    return n.length >= 6 && m.length >= 6 && (m.endsWith(n) || n.endsWith(m));
  });
}

/* feed provider slug → our registry name (for the BYOK connected badge) */
const REGISTRY_ALIAS: Record<string, string> = { vertex_ai: 'gemini', together_ai: 'together' };

export const registryName = (p: string) => REGISTRY_ALIAS[p] ?? p;

const PRETTY: Record<string, string> = {
  '': 'Unknown',
  azure: 'Azure OpenAI',
  azure_ai: 'Azure OpenAI',
  bedrock: 'AWS Bedrock',
  vertex_ai: 'Vertex AI',
  together_ai: 'Together',
  fireworks_ai: 'Fireworks AI',
  openrouter: 'OpenRouter',
  deepinfra: 'DeepInfra',
  xai: 'xAI',
  vercel_ai_gateway: 'Vercel AI Gateway',
  replicate: 'Replicate',
  gmi: 'GMI',
  github_copilot: 'GitHub Copilot',
  gradient_ai: 'Gradient AI',
};

export function prettyProvider(p: string): string {
  if (PRETTY[p]) return PRETTY[p];
  return p.replace(/_/g, ' ').replace(/\b[a-z]/g, (c) => c.toUpperCase());
}

/* Cheapest list price per registry provider — powers "from $x/1M" on the
   Top Providers card. */
export function cheapestByProvider(entries: PriceEntry[]): Map<string, PriceEntry> {
  const best = new Map<string, PriceEntry>();
  for (const e of entries) {
    const key = registryName(e.provider);
    const cur = best.get(key);
    if (!cur || e.inPerM < cur.inPerM) best.set(key, e);
  }
  return best;
}

/* $0.0042 → "$0.0042", $2.5 → "$2.50" */
export const fmtUsd = (x: number) => `$${x >= 0.01 ? x.toFixed(2) : x.toFixed(4)}`;

export const isFree = (e: { inPerM: number; outPerM: number }) => e.inPerM === 0 && e.outPerM === 0;

/* Where a row's provider sells this model — OpenRouter page or the feed's own
   docs URL. No guessed URLs: only what the feeds give us. */
export function entryUrl(e: PriceEntry): string | null {
  if (e.provider === 'openrouter') return `https://openrouter.ai/${e.model.replace(/^openrouter\//, '')}`;
  return e.source ?? null;
}

/* Best link for a model: its OpenRouter page, else a feed-provided docs URL. */
export function modelUrl(entries: PriceEntry[], modelId: string): string | null {
  const m = pricesFor(entries, modelId);
  const or = m.find((e) => e.provider === 'openrouter');
  if (or) return entryUrl(or);
  return m.map(entryUrl).find((u): u is string => u !== null) ?? null;
}

/* Registry/feed provider → its official OpenRouter provider page (slugs come
   from the providers API, so nothing is guessed), else any feed-provided docs
   URL for that provider, else the provider directory. */
const URL_ALIAS: Record<string, string> = { gemini: 'Google', mercury: 'Inception', bedrock: 'Amazon Bedrock' };

export function providerUrl(registry: string, data?: MarketData | null): string {
  const reg = registryName(registry);
  const candidates = [norm(URL_ALIAS[registry] ?? reg), norm(prettyProvider(reg))];
  for (const k of candidates) {
    const hit = data?.providers.get(k) ?? data?.providers.get(k.replace(/ai$/, ''));
    if (hit) return `https://openrouter.ai/providers/${hit.slug}`;
  }
  const src = data?.entries.find((e) => registryName(e.provider) === reg && e.source)?.source;
  if (src) return src;
  return 'https://openrouter.ai/providers';
}
