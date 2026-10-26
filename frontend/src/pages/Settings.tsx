import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { API_URL, api, displayName, displayColor, providerDisplay, type ApiKey, type ApiKeyCreated } from '../lib/api';
import { changePassword } from '../lib/auth';
import { signOut } from '../lib/nav';
import { DashPage } from '../components/dashboard/DashPage';
import { ChartCard } from '../components/dashboard/ChartCard';
import { CopyField } from '../components/ui/CopyField';
import { CodeSnippet } from '../components/ui/CodeSnippet';
import { timeAgo, useEscape } from '../lib/utils';
import { Eye, EyeOff, KeyRound, Plus, Trash2, TriangleAlert, X } from 'lucide-react';

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

  // closing the form also drops the ?add=1 deep link so a reload starts closed
  const closeForm = () => {
    setOpen(false);
    setErr('');
    const u = new URL(window.location.href);
    if (u.searchParams.has('add')) {
      u.searchParams.delete('add');
      window.history.replaceState({}, '', u);
    }
  };

  useEscape(open, closeForm);
  useEscape(disconnectModal.open, () => setDisconnectModal({ provider: null, open: false }));

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
      closeForm();
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
          <button
            onClick={() => setOpen(true)}
            className="mt-4 h-9 px-4 rounded-lg text-[13px] font-semibold text-white transition-all hover:opacity-90 active:scale-[0.98]"
            style={{ background: 'var(--purple)' }}
          >
            Connect a provider key
          </button>
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
          <button
            onClick={() => setOpen(true)}
            className="inline-flex items-center gap-1 h-7 px-2.5 rounded-full text-[12px] font-medium border border-dashed border-[var(--border-strong)] text-[var(--text-muted)] hover:text-[var(--accent)] hover:border-[var(--accent)] transition-colors"
          >
            <Plus className="w-3 h-3" /> Add key
          </button>
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
              onClick={closeForm}
              className="h-9 px-4 rounded-lg text-[13px] font-medium text-[var(--text-muted)] border border-[var(--border)] hover:bg-[var(--hover)] hover:text-[var(--text-primary)] transition-colors"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {disconnectModal.open && disconnectModal.provider && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60" onClick={closeDisconnectModal}>
          <div role="dialog" aria-modal="true" aria-label="Disconnect provider" className="w-full max-w-sm mx-4 p-6 rounded-2xl shadow-2xl" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }} onClick={(e) => e.stopPropagation()}>
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

/* Gateway API keys - what apps use to call ReRoute. Session-only management:
   a leaked key can call /v1 but cannot mint or list keys. */
function GatewayKeys() {
  const { data, refetch } = useQuery({ queryKey: ['api-keys'], queryFn: () => api.listApiKeys() });
  const [createOpen, setCreateOpen] = useState(false);
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [created, setCreated] = useState<ApiKeyCreated | null>(null);
  const [revokeTarget, setRevokeTarget] = useState<ApiKey | null>(null);

  const rows = data ?? [];
  const FIELD =
    'w-full h-9 px-3 rounded-lg text-[13px] text-[var(--text-primary)] bg-black border border-[var(--border)] outline-none transition-colors placeholder:text-[var(--text-faint)] focus:border-[var(--accent)]';

  const closeCreate = () => {
    setCreateOpen(false);
    setCreated(null);
    setErr('');
    setName('');
  };

  // the reveal step is not Escape-dismissable - that would lose the only copy of the key
  useEscape(createOpen && !created, closeCreate);
  useEscape(!!revokeTarget, () => setRevokeTarget(null));

  const create = async () => {
    if (busy || !name.trim()) return;
    setBusy(true);
    setErr('');
    try {
      const key = await api.createApiKey(name.trim());
      setCreated(key);
      setName('');
      await refetch();
    } catch (e) {
      setErr(e instanceof Error ? e.message : 'Could not create key');
    } finally {
      setBusy(false);
    }
  };

  const revoke = async () => {
    if (!revokeTarget) return;
    await api.revokeApiKey(revokeTarget.id);
    setRevokeTarget(null);
    await refetch();
  };

  return (
    <ChartCard
      title="Gateway API keys"
      subtitle="Credentials your apps use to call ReRoute"
      action={
        <button
          onClick={() => setCreateOpen(true)}
          className="h-8 px-3 rounded-lg text-[12px] font-semibold text-black transition-all hover:opacity-90 active:scale-[0.98]"
          style={{ background: 'var(--accent)' }}
        >
          Create key
        </button>
      }
    >
      <div className="px-4 pb-4 mt-2">
        {rows.length === 0 ? (
          <div className="flex flex-col items-center text-center py-9 rounded-xl border border-dashed border-[var(--border)]">
            <span
              className="w-10 h-10 rounded-full flex items-center justify-center mb-3"
              style={{ background: 'var(--accent-dim)' }}
            >
              <KeyRound className="w-5 h-5" style={{ color: 'var(--accent)' }} />
            </span>
            <p className="text-[13px] font-semibold text-[var(--text-primary)]">No gateway keys yet</p>
            <p className="text-[12px] text-[var(--text-muted)] mt-1 max-w-[360px] leading-relaxed">
              Create one and point any OpenAI-compatible client at this gateway - every request lands in
              analytics with tokens, cost and latency.
            </p>
          </div>
        ) : (
          <div className="rounded-xl overflow-hidden" style={{ border: '1px solid var(--border)' }}>
            {rows.map((k) => (
              <div
                key={k.id}
                className="flex items-center gap-3 px-3.5 py-3 border-b border-[var(--border)] last:border-b-0"
              >
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="text-[13px] font-semibold text-[var(--text-primary)] truncate">
                      {k.name}
                    </span>
                    <span
                      className="w-1.5 h-1.5 rounded-full shrink-0"
                      style={{ background: k.revoked_at ? 'var(--text-faint)' : 'var(--accent)' }}
                    />
                    <span
                      className="text-[11px] shrink-0"
                      style={{ color: k.revoked_at ? 'var(--text-faint)' : 'var(--accent)' }}
                    >
                      {k.revoked_at ? 'Revoked' : 'Active'}
                    </span>
                  </div>
                  <div className="flex items-center gap-1.5 mt-0.5 text-[11px] text-[var(--text-muted)] flex-wrap">
                    <code className="font-mono">{k.key_prefix}••••</code>
                    <span className="text-[var(--text-faint)]">·</span>
                    <span>last used {timeAgo(k.last_used_at)}</span>
                    <span className="text-[var(--text-faint)]">·</span>
                    <span>created {timeAgo(k.created_at)}</span>
                  </div>
                </div>
                {!k.revoked_at && (
                  <button
                    onClick={() => setRevokeTarget(k)}
                    aria-label={`Revoke ${k.name}`}
                    className="p-1.5 rounded-md text-[var(--text-faint)] hover:text-[var(--danger)] hover:bg-[var(--hover)] transition-colors"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {createOpen && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 p-4" onClick={created ? undefined : closeCreate}>
          <div
            role="dialog"
            aria-modal="true"
            aria-label={created ? 'Copy your API key' : 'Create API key'}
            className="w-full max-w-md p-6 rounded-2xl shadow-2xl"
            style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}
            onClick={(e) => e.stopPropagation()}
          >
            {created ? (
              <>
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-semibold text-white">Copy your key</h3>
                  <button onClick={closeCreate} aria-label="Close" className="text-[var(--text-muted)] hover:text-white transition-colors">
                    <X className="w-5 h-5" />
                  </button>
                </div>
                <p
                  className="flex items-start gap-2 p-2.5 mb-3 rounded-lg text-[12px] leading-relaxed"
                  style={{ background: 'var(--warning-dim)', border: '1px solid rgba(214,168,76,0.35)', color: '#E8C97F' }}
                >
                  <TriangleAlert className="w-3.5 h-3.5 mt-px shrink-0" />
                  <span>Shown once. Store it now - it cannot be recovered, only revoked.</span>
                </p>
                <CopyField value={created.key} />
                <p className="text-[11px] text-[var(--text-muted)] mt-4 mb-2">
                  Point any OpenAI-compatible client here:
                </p>
                <CodeSnippet apiKey={created.key} />
                <button
                  onClick={closeCreate}
                  className="w-full h-10 mt-4 rounded-lg text-sm font-medium text-white border border-[var(--border)] hover:bg-[var(--hover)] transition-colors"
                >
                  Done - I copied it
                </button>
              </>
            ) : (
              <>
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-semibold text-white">Create API key</h3>
                  <button onClick={closeCreate} aria-label="Close" className="text-[var(--text-muted)] hover:text-white transition-colors">
                    <X className="w-5 h-5" />
                  </button>
                </div>
                <label className="block">
                  <span className="block text-[12px] font-medium text-[var(--text-secondary)] mb-1.5">
                    Name - so you can tell keys apart
                  </span>
                  <input
                    autoFocus
                    value={name}
                    onChange={(e) => { setName(e.target.value); if (err) setErr(''); }}
                    onKeyDown={(e) => e.key === 'Enter' && create()}
                    placeholder="laptop, backend-prod, cursor..."
                    maxLength={64}
                    className={FIELD}
                    autoComplete="off"
                    spellCheck={false}
                  />
                </label>
                {err && (
                  <p
                    className="flex items-start gap-2 p-2.5 mt-3 rounded-lg text-[12px] leading-relaxed"
                    style={{ background: 'var(--danger-dim)', border: '1px solid rgba(229,83,75,0.35)', color: '#FCA5A5' }}
                  >
                    <TriangleAlert className="w-3.5 h-3.5 mt-px shrink-0" />
                    <span>{err}</span>
                  </p>
                )}
                <div className="flex gap-2 mt-5">
                  <button
                    onClick={closeCreate}
                    className="flex-1 h-10 rounded-lg text-sm font-medium text-white border border-[var(--border)] hover:bg-[var(--hover)] transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={create}
                    disabled={busy || !name.trim()}
                    className="flex-1 h-10 rounded-lg text-sm font-semibold text-black transition-all disabled:opacity-40 disabled:pointer-events-none active:scale-[0.98] hover:opacity-90"
                    style={{ background: 'var(--accent)' }}
                  >
                    {busy ? 'Creating.' : 'Create key'}
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {revokeTarget && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 p-4" onClick={() => setRevokeTarget(null)}>
          <div
            role="dialog"
            aria-modal="true"
            aria-label="Revoke API key"
            className="w-full max-w-sm p-6 rounded-2xl shadow-2xl"
            style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-white">Revoke key</h3>
              <button onClick={() => setRevokeTarget(null)} aria-label="Close" className="text-[var(--text-muted)] hover:text-white transition-colors">
                <X className="w-5 h-5" />
              </button>
            </div>
            <p className="text-sm text-[var(--text-muted)] mb-4">
              Revoke <strong className="text-white">{revokeTarget.name}</strong>? Any app using it stops
              working immediately.
            </p>
            <div className="flex gap-2">
              <button onClick={() => setRevokeTarget(null)} className="flex-1 h-10 rounded-lg text-sm font-medium text-white border border-[var(--border)] hover:bg-[var(--hover)] transition-colors">
                Cancel
              </button>
              <button onClick={revoke} className="flex-1 h-10 rounded-lg text-sm font-medium text-white transition-all hover:opacity-90 active:scale-[0.98]" style={{ background: 'var(--danger)' }}>
                Revoke
              </button>
            </div>
          </div>
        </div>
      )}
    </ChartCard>
  );
}

export default function SettingsPage() {
  return (
    <DashPage title="Settings" sub="Gateway keys, provider keys, and account security">
      <div className="space-y-4">
        {/* Gateway API keys - what apps authenticate with */}
        <GatewayKeys />

        {/* Connection details for any OpenAI-compatible client */}
        <ChartCard title="Connection" subtitle="Point any OpenAI-compatible client here">
          <div className="px-4 pb-4 mt-2 space-y-3">
            <div>
              <label className="text-[11px] text-[var(--text-muted)] block mb-1">Gateway URL</label>
              <CopyField value={`${API_URL}/v1`} />
            </div>
            <div>
              <label className="text-[11px] text-[var(--text-muted)] block mb-1">Default model</label>
              <CopyField value="mercury-2" />
            </div>
            <div className="flex items-center gap-2 text-[11px] text-[var(--text-muted)]">
              <span className="w-1.5 h-1.5 rounded-full bg-[var(--accent)]" />
              {import.meta.env.PROD ? 'Production' : 'Development'}
              <Link to="/status" className="ml-auto underline decoration-[var(--text-faint)] underline-offset-2 hover:text-[var(--text-primary)] transition-colors">
                Status
              </Link>
              <Link to="/docs" className="underline decoration-[var(--text-faint)] underline-offset-2 hover:text-[var(--text-primary)] transition-colors">
                Quickstart
              </Link>
            </div>
          </div>
        </ChartCard>

        {/* Providers (per-user BYOK) */}
        <ChartCard title="Provider keys (BYOK)" subtitle="Stored server-side - your apps never need these">
          <Providers />
        </ChartCard>

        {/* Account security */}
        <ChartCard title="Password">
          <Password />
        </ChartCard>
      </div>
    </DashPage>
  );
}

