import { Link } from 'react-router-dom';
import { API_URL } from '../lib/api';
import { CopyField } from '../components/ui/CopyField';
import { CodeSnippet } from '../components/ui/CodeSnippet';

const STEPS: { title: string; body: string }[] = [
  { title: 'Create a gateway key', body: 'Settings → Gateway API keys → Create key. It is shown once.' },
  { title: 'Connect a provider', body: 'Settings → Provider keys. ReRoute stores it server-side; your code never sees it.' },
  { title: 'Point your client here', body: 'Use the base URL below with the gateway key as the bearer token.' },
];

export default function Docs() {
  return (
    <div className="container-x py-16 max-w-3xl">
      <p className="text-[11px] uppercase tracking-wider text-[var(--text-faint)]">Quickstart</p>
      <h1 className="text-[26px] font-bold text-white mt-2">One endpoint, every provider</h1>
      <p className="text-[14px] text-[var(--text-muted)] mt-2 leading-relaxed">
        ReRoute speaks the OpenAI chat-completions API, so any compatible client works. Only traffic sent
        here is tracked in your dashboard.
      </p>

      <div className="mt-8 space-y-4">
        <div>
          <label className="text-[11px] text-[var(--text-muted)] block mb-1">Base URL</label>
          <CopyField value={`${API_URL}/v1`} />
        </div>
        <div>
          <label className="text-[11px] text-[var(--text-muted)] block mb-1">Authorization</label>
          <CopyField value="Bearer rr_live_…" />
        </div>
      </div>

      <div className="mt-8">
        <CodeSnippet apiKey="rr_live_YOUR_KEY" />
      </div>

      <div className="mt-10 grid gap-3 sm:grid-cols-3">
        {STEPS.map((s, i) => (
          <div key={s.title} className="card p-4">
            <span className="text-[11px] font-mono text-[var(--text-faint)]">0{i + 1}</span>
            <p className="text-[13px] font-semibold text-[var(--text-primary)] mt-1">{s.title}</p>
            <p className="text-[12px] text-[var(--text-muted)] mt-1 leading-relaxed">{s.body}</p>
          </div>
        ))}
      </div>

      <div className="mt-10 rounded-xl p-4 text-[12px] leading-relaxed text-[var(--text-muted)]"
        style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
        <p className="text-[var(--text-primary)] font-semibold text-[13px] mb-1">What you get back</p>
        <p>
          Each request is audited with tokens, cost, latency, time-to-first-token, cache hits and finish
          reason. Identical prompts are served from the semantic cache - streamed or not.
        </p>
        <p className="mt-2">
          Calling a provider directly bypasses all of this. There is nothing to import afterwards.
        </p>
      </div>

      <p className="text-[12px] text-[var(--text-muted)] mt-8">
        Need a key?{' '}
        <Link to="/dashboard/settings" className="text-[var(--accent)] underline underline-offset-2">
          Open Settings
        </Link>
        .
      </p>
    </div>
  );
}
