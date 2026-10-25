import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api, displayName, displayColor, providerDisplay } from '../lib/api';
import { changePassword } from '../lib/auth';
import { signOut } from '../lib/nav';
import { DashPage } from '../components/dashboard/DashPage';
import { ChartCard } from '../components/dashboard/ChartCard';
import { Eye, EyeOff, KeyRound, Trash2, TriangleAlert, X } from 'lucide-react';

/* Self-service password change — proves current password, rotates every session */
function Password() {
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [confirm, setConfirm] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [ok, setOk] = useState(false);

  const inputCls =
    'h-8 px-3 rounded-lg text-[12px] text-[var(--text-primary)] outline-none bg-black border border-[var(--border)] focus:border-[var(--accent)] transition-colors';

  const submit = async () => {
    if (busy) return;
    if (next !== confirm) { setErr('Passwords do not match'); return; }
    setBusy(true);
    setErr('');
    setOk(false);
    try {
      await changePassword(current, next);
      setCurrent(''); setNext(''); setConfirm('');
      setOk(true);
    } catch (e) {
      setErr(e instanceof Error ? e.message : 'Could not change password');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="px-4 pb-4 mt-2">
      <div className="flex flex-wrap items-center gap-2">
        <input type="password" value={current} onChange={(e) => { setCurrent(e.target.value); if (err) setErr(''); }}
          placeholder="Current password" className={`${inputCls} flex-1 min-w-[150px]`} autoComplete="current-password" />
        <input type="password" value={next} onChange={(e) => { setNext(e.target.value); if (err) setErr(''); }}
          placeholder="New password (7+ chars)" className={`${inputCls} flex-1 min-w-[150px]`} autoComplete="new-password" />
        <input type="password" value={confirm} onChange={(e) => { setConfirm(e.target.value); if (err) setErr(''); }}
          onKeyDown={(e) => e.key === 'Enter' && submit()}
          placeholder="Confirm new password" className={`${inputCls} flex-1 min-w-[150px]`} autoComplete="new-password" />
        <button onClick={submit} disabled={busy || !current || next.length < 7}
          className="h-8 px-3 rounded-lg text-[12px] font-medium text-black bg-[var(--accent)] hover:opacity-90 disabled:opacity-40 transition-opacity">
          {busy ? 'Updating…' : 'Change password'}
        </button>
      </div>
      {err && <p className="text-[11px] text-[var(--danger)] mt-2">{err}</p>}
      {ok && <p className="text-[11px] mt-2" style={{ color: 'var(--accent)' }}>Password changed. Other sessions were signed out.</p>}
    </div>
  );
}

/* Per-user BYOK — this account's provider keys (write-only, server returns masked) */
function Providers() {
  // deep-link: dashboard "Add your key" lands here with the form open
  const [open, setOpen] = useState(() => new URLSearchParams(window.location.search).get('add') === '1');
  const [provider, setProvider] = useState('openai');
  const [apiKey, setApiKey] = useState('');
  const [baseUrl, setBaseUrl] = useState('');
  const [showKey, setShowKey] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');

  // Disconnect modal state
  const [disconnectModal, setDisconnectModal] = useState<{ provider: string | null; open: boolean }>({
    provider: null,
    open: false,
  });

  const { data, refetch, isError, error } = useQuery({
    queryKey: ['providers'],
    queryFn: () => api.listProviders(),
  });

  if (isError) {
    const unauthorized = /401/.test(String(error));
    return (
      <div className="px-4 pb-4 mt-2 text-center">
        <p className="text-[13px] text-[var(--text-primary)] mb-1">
          {unauthorized ? 'Session expired' : 'Could not load providers'}
        </p>
        <p className="text-[11px] text-[var(--text-muted)] mb-3">
          {unauthorized ? 'Your session expired — sign in again.' : 'Could not reach the gateway API.'}
        </p>
        <button onClick={signOut} className="h-8 px-3 rounded-lg text-[11px] font-medium text-[var(--text-muted)] border border-[var(--border)] hover:bg-[var(--hover)] hover:text-[var(--text-primary)] transition-colors">
          Sign out
        </button>
      </div>
    );
  }

  const connect = async () => {
    if (busy) return;
    setBusy(true);
    setErr('');
    try {
      await api.connectProvider(provider, apiKey.trim(), baseUrl.trim() || undefined);
      setApiKey('');
      setBaseUrl('');
      setOpen(false);
      await refetch();
    } catch (e) {
      const msg = String(e instanceof Error ? e.message : e);
      setErr(/"detail":\s*"([^"]+)"/.exec(msg)?.[1] ?? msg);
    } finally {
      setBusy(false);
    }
  };

  const openDisconnectModal = (p: string) => {
    setDisconnectModal({ provider: p, open: true });
  };

  const confirmDisconnect = async () => {
    if (!disconnectModal.provider) return;
    await api.disconnectProvider(disconnectModal.provider);
    setDisconnectModal({ provider: null, open: false });
    await refetch();
  };

  const closeDisconnectModal = () => {
    setDisconnectModal({ provider: null, open: false });
  };

  const connected = data ?? [];
  const FIELD =
    'w-full h-9 px-3 rounded-lg text-[13px] text-[var(--text-primary)] bg-black border border-[var(--border)] outline-none transition-colors placeholder:text-[var(--text-faint)] focus:border-[var(--purple)]';

  return (
    <div className="px-4 pb-4 mt-2">
      <p className="text-[12px] text-[var(--text-muted)] mb-3">
        Bring your own keys — requests route through your accounts, and keys stay masked &amp; encrypted.
      </p>

      {connected.length === 0 && !open ? (
        <div className="flex flex-col items-center text-center py-9 rounded-xl border border-dashed border-[var(--border)]">
          <span className="w-10 h-10 rounded-full flex items-center justify-center mb-3" style={{ background: 'var(--purple-dim)' }}>
            <KeyRound className="w-5 h-5" style={{ color: 'var(--purple)' }} />
          </span>
          <p className="text-[13px] font-semibold text-[var(--text-primary)]">No provider keys yet</p>
          <p className="text-[12px] text-[var(--text-muted)] mt-1 max-w-[340px] leading-relaxed">
            Connect OpenAI, Anthropic, Groq… to start routing through your own accounts — usage and cost land in this dashboard.
          </p>
        </div>
      ) : (
        <div className="flex items-center gap-2 flex-wrap">
          {connected.map((tp) => (
            <span
              key={tp.provider}
              className="inline-flex items-center gap-1.5 h-7 pl-2.5 pr-1.5 rounded-full text-[12px] border"
              style={{ borderColor: displayColor(tp.provider), color: displayColor(tp.provider) }}
            >
              <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: displayColor(tp.provider) }} />
              {displayName(tp.provider)}
              <code className="font-mono text-[10px] text-[var(--text-muted)]">{tp.key_masked}</code>
              <button
                onClick={() => openDisconnectModal(tp.provider)}
                title={`Disconnect ${displayName(tp.provider)}`}
                className="px-1 text-[var(--text-faint)] hover:text-[var(--danger)] transition-colors"
              >
                <Trash2 className="w-3 h-3" />
              </button>
            </span>
          ))}
        </div>
      )}

      {open && (
        <div className="mt-3 rounded-xl p-4" style={{ background: 'var(--bg-base)', border: '1px solid var(--border)' }}>
          <div className="grid grid-cols-1 sm:grid-cols-[150px_1fr] gap-3">
            <label className="block">
              <span className="block text-[12px] font-medium text-[var(--text-secondary)] mb-1.5">Provider</span>
              <div className="relative">
                <select
                  value={provider}
                  onChange={(e) => setProvider(e.target.value)}
                  className={`${FIELD} pr-8 appearance-none`}
                >
                  {Object.keys(providerDisplay).map((p) => (
                    <option key={p} value={p}>{displayName(p)}</option>
                  ))}
                </select>
                <span className="absolute right-3 top-1/2 -translate-y-1/2 w-1.5 h-1.5 rounded-full pointer-events-none" style={{ background: displayColor(provider) }} />
              </div>
            </label>
            <label className="block">
              <span className="block text-[12px] font-medium text-[var(--text-secondary)] mb-1.5">API key</span>
              <div className="relative">
                <input
                  type={showKey ? 'text' : 'password'}
                  value={apiKey}
                  onChange={(e) => { setApiKey(e.target.value); if (err) setErr(''); }}
                  onKeyDown={(e) => e.key === 'Enter' && connect()}
                  placeholder={provider === 'ollama' ? 'Optional for local Ollama' : `Paste your ${displayName(provider)} API key`}
                  className={`${FIELD} pr-10`}
                  autoComplete="off"
                  spellCheck={false}
                />
                <button
                  type="button"
                  onClick={() => setShowKey(!showKey)}
                  tabIndex={-1}
                  aria-label={showKey ? 'Hide key' : 'Show key'}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[var(--text-faint)] hover:text-[var(--text-secondary)] transition-colors"
                >
                  {showKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </label>
          </div>
          <label className="block mt-3">
            <span className="block text-[12px] font-medium text-[var(--text-secondary)] mb-1.5">
              Base URL <span className="font-normal text-[var(--text-faint)]">— optional, for Ollama or a custom endpoint</span>
            </span>
            <input
              value={baseUrl}
              onChange={(e) => { setBaseUrl(e.target.value); if (err) setErr(''); }}
              onKeyDown={(e) => e.key === 'Enter' && connect()}
              placeholder="http://localhost:11434/v1"
              className={FIELD}
              spellCheck={false}
            />
          </label>

          {err && (
            <p className="flex items-start gap-2 p-2.5 mt-3 rounded-lg text-[12px] leading-relaxed"
              style={{ background: 'var(--danger-dim)', border: '1px solid rgba(229,83,75,0.35)', color: '#FCA5A5' }}>
              <TriangleAlert className="w-3.5 h-3.5 mt-px shrink-0" />
              <span>{err}</span>
            </p>
          )}

          <div className="flex items-center gap-2 mt-4">
            <button
              onClick={connect}
              disabled={busy || (!apiKey.trim() && !baseUrl.trim())}
              className="h-9 px-4 rounded-lg text-[13px] font-semibold text-white transition-all disabled:opacity-40 disabled:pointer-events-none active:scale-[0.98] hover:opacity-90"
              style={{ background: 'var(--purple)' }}
            >
              {busy ? 'Verifying…' : 'Connect key'}
            </button>
            <button
              onClick={() => { setOpen(false); setErr(''); }}
              className="h-9 px-4 rounded-lg text-[13px] font-medium text-[var(--text-muted)] border border-[var(--border)] hover:bg-[var(--hover)] hover:text-[var(--text-primary)] transition-colors"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {disconnectModal.open && disconnectModal.provider && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60" onClick={closeDisconnectModal}>
          <div className="w-full max-w-sm mx-4 p-6 rounded-2xl shadow-2xl" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }} onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-white">Disconnect provider</h3>
              <button onClick={closeDisconnectModal} className="text-[var(--text-muted)] hover:text-white transition-colors">
                <X className="w-5 h-5" />
              </button>
            </div>
            <p className="text-sm text-[var(--text-muted)] mb-4">
              Disconnect <strong className="text-white">{displayName(disconnectModal.provider)}</strong>? Its models will stop being available to you.
            </p>
            <div className="flex gap-2">
              <button onClick={closeDisconnectModal} className="flex-1 h-10 rounded-lg text-sm font-medium text-white border border-[var(--border)] hover:bg-[var(--hover)] transition-colors">Cancel</button>
              <button onClick={confirmDisconnect} className="flex-1 h-10 rounded-lg text-sm font-medium text-white transition-all hover:opacity-90 active:scale-[0.98]" style={{ background: 'var(--danger)' }}>
                Disconnect
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function SettingsPage() {
  return (
    <DashPage title="Settings" sub="Your API keys — masked & encrypted">
      <div className="space-y-4">
        {/* Providers (per-user BYOK) */}
        <ChartCard title="Your keys">
          <Providers />
        </ChartCard>

        {/* Account security */}
        <ChartCard title="Password">
          <Password />
        </ChartCard>

        {/* General settings */}
        <ChartCard title="General">
          <div className="px-4 pb-4 space-y-3 mt-2">
            <div>
              <label className="text-[11px] text-[var(--text-muted)] block mb-1">Gateway URL</label>
              <div className="flex items-center gap-2 h-8 px-3 rounded-lg border border-[var(--border)] bg-black">
                <span className="text-[12px] text-[var(--text-muted)] font-mono flex-1">{window.location.origin.replace(/:\d+$/, ':8000')}</span>
              </div>
            </div>
            <div>
              <label className="text-[11px] text-[var(--text-muted)] block mb-1">Environment</label>
              <div className="flex items-center gap-2 h-8 px-3 rounded-lg border border-[var(--border)] bg-black">
                <span className="w-1.5 h-1.5 rounded-full bg-[var(--accent)]" />
                <span className="text-[12px] text-[var(--text-primary)]">Development</span>
              </div>
            </div>
          </div>
        </ChartCard>
      </div>
    </DashPage>
  );
}
