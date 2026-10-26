import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api, type UserInfo } from '../lib/api';
import { storedUser } from '../lib/auth';
import { signOut } from '../lib/nav';
import { DashPage } from '../components/dashboard/DashPage';
import { ChartCard } from '../components/dashboard/ChartCard';
import { useEscape } from '../lib/utils';
import { Check, Plus, Trash2, KeyRound, X } from 'lucide-react';

const inputCls =
  'h-8 px-3 rounded-lg text-[12px] text-[var(--text-primary)] outline-none bg-black border border-[var(--border)] focus:border-[var(--accent)] transition-colors';

const detailOf = (e: unknown) =>
  /"detail":\s*"([^"]+)"/.exec(String(e instanceof Error ? e.message : e))?.[1] ??
  String(e instanceof Error ? e.message : e);

const shortDate = (iso: string | null) => {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) +
    ' ' + d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
};

/* Accounts — admin-only (the backend 403s members either way) */
export default function UsersPage() {
  const me = storedUser();
  const { data, refetch, isError, error } = useQuery({
    queryKey: ['users'],
    queryFn: api.listUsers,
  });

  const [open, setOpen] = useState(false);
  const [email, setEmail] = useState('');
  const [pw, setPw] = useState('');
  const [role, setRole] = useState<'admin' | 'member'>('member');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');

  // Password reset modal state
  const [resetModal, setResetModal] = useState<{ user: UserInfo | null; open: boolean }>({
    user: null,
    open: false,
  });
  const [resetPw, setResetPw] = useState('');
  const [resetConfirm, setResetConfirm] = useState('');
  const [resetBusy, setResetBusy] = useState(false);
  const [resetErr, setResetErr] = useState('');
  const [resetOk, setResetOk] = useState(false);

  const create = async () => {
    if (busy) return;
    setBusy(true);
    setErr('');
    try {
      await api.createUser(email.trim(), pw, role);
      setEmail('');
      setPw('');
      setOpen(false);
      await refetch();
    } catch (e) {
      setErr(detailOf(e));
    } finally {
      setBusy(false);
    }
  };

  const patch = async (u: UserInfo, body: { role?: string; is_active?: boolean }) => {
    setErr('');
    try {
      await api.updateUser(u.id, body);
      await refetch();
    } catch (e) {
      setErr(detailOf(e));
    }
  };

  const resetPassword = async (u: UserInfo) => {
    setResetModal({ user: u, open: true });
    setResetPw('');
    setResetConfirm('');
    setResetErr('');
    setResetOk(false);
  };

  const confirmResetPassword = async () => {
    if (resetBusy || !resetModal.user) return;
    if (resetPw !== resetConfirm) { setResetErr('Passwords do not match'); return; }
    if (resetPw.length < 7) { setResetErr('Password must be at least 7 characters'); return; }
    setResetBusy(true);
    setResetErr('');
    try {
      await api.resetUserPassword(resetModal.user.id, resetPw);
      setResetOk(true);
      window.setTimeout(() => setResetModal({ user: null, open: false }), 1600);
    } catch (e) {
      setResetErr(detailOf(e));
    } finally {
      setResetBusy(false);
    }
  };

  const closeResetModal = () => {
    setResetModal({ user: null, open: false });
    setResetPw('');
    setResetConfirm('');
    setResetErr('');
    setResetOk(false);
  };

  useEscape(resetModal.open, closeResetModal);

  const remove = async (u: UserInfo) => {
    if (!window.confirm(`Delete ${u.email}? This cannot be undone.`)) return;
    setErr('');
    try {
      await api.deleteUser(u.id);
      await refetch();
    } catch (e) {
      setErr(detailOf(e));
    }
  };

  if (isError) {
    const unauthorized = /401|403/.test(String(error));
    return (
      <DashPage title="Users" sub="Accounts, roles & access">
        <div className="px-4 pb-4 text-center">
          <p className="text-[13px] text-[var(--text-primary)] mb-1">
            {unauthorized ? 'Not available' : 'Could not load users'}
          </p>
          <p className="text-[11px] text-[var(--text-muted)] mb-3">
            {unauthorized ? 'Your session does not have admin access.' : 'Is the backend running?'}
          </p>
          <button onClick={signOut} className="h-8 px-3 rounded-lg text-[11px] font-medium text-[var(--text-muted)] border border-[var(--border)] hover:bg-[var(--hover)] hover:text-[var(--text-primary)] transition-colors">
            Sign out
          </button>
        </div>
      </DashPage>
    );
  }

  const users = data ?? [];

  return (
    <DashPage title="Users" sub="Accounts, roles & access">
      <div className="space-y-4">
        <ChartCard title="Accounts">
          <div className="px-4 pb-4 mt-2">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-[11px] text-[var(--text-muted)]">{users.length} accounts</span>
              <button
                onClick={() => setOpen(!open)}
                className="h-6 px-2 rounded-full text-[11px] font-medium border border-[var(--border)] text-[var(--text-muted)] hover:border-[var(--accent)] hover:text-[var(--accent)] transition-colors flex items-center gap-1"
              >
                <Plus className="w-3 h-3" /> New user
              </button>
            </div>
            {open && (
              <div className="flex flex-wrap items-center gap-2 mt-2">
                <input
                  type="email"
                  value={email}
                  onChange={(e) => { setEmail(e.target.value); if (err) setErr(''); }}
                  onKeyDown={(e) => e.key === 'Enter' && create()}
                  placeholder="Email"
                  className={`${inputCls} flex-1 min-w-[160px]`}
                />
                <input
                  type="password"
                  value={pw}
                  onChange={(e) => { setPw(e.target.value); if (err) setErr(''); }}
                  onKeyDown={(e) => e.key === 'Enter' && create()}
                  placeholder="Password (7+ chars)"
                  className={`${inputCls} flex-1 min-w-[160px]`}
                />
                <select
                  value={role}
                  onChange={(e) => setRole(e.target.value as 'admin' | 'member')}
                  className={`${inputCls} pr-6`}
                >
                  <option value="member">Member (read-only)</option>
                  <option value="admin">Admin</option>
                </select>
                <button
                  onClick={create}
                  disabled={busy || !/.+@.+\..+/.test(email) || pw.length < 7}
                  className="h-8 px-3 rounded-lg text-[12px] font-medium text-black bg-[var(--accent)] hover:opacity-90 disabled:opacity-40 transition-opacity"
                >
                  {busy ? 'Creating…' : 'Create'}
                </button>
              </div>
            )}
            {err && <p className="text-[11px] text-[var(--danger)] mt-2">{err}</p>}
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="text-[10px] uppercase tracking-wider text-[var(--text-faint)] border-t border-[var(--border)]">
                  <th className="px-4 py-2 font-medium">User</th>
                  <th className="px-4 py-2 font-medium">Role</th>
                  <th className="px-4 py-2 font-medium">Status</th>
                  <th className="px-4 py-2 font-medium">Last login</th>
                  <th className="px-4 py-2 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id} className="border-t border-[var(--border)] text-[12px]">
                    <td className="px-4 py-2.5 text-[var(--text-primary)]">
                      {u.email}
                      {u.id === me?.id && <span className="ml-2 text-[10px] text-[var(--text-faint)]">you</span>}
                    </td>
                    <td className="px-4 py-2.5">
                      <span className="text-[10px] uppercase tracking-wider px-1.5 py-0.5 rounded border"
                        style={{ borderColor: u.role === 'admin' ? 'var(--accent)' : 'var(--border)', color: u.role === 'admin' ? 'var(--accent)' : 'var(--text-muted)' }}>
                        {u.role}
                      </span>
                    </td>
                    <td className="px-4 py-2.5" style={{ color: u.is_active ? 'var(--text-secondary)' : 'var(--danger)' }}>
                      {u.is_active ? 'Active' : 'Suspended'}
                    </td>
                    <td className="px-4 py-2.5 text-[var(--text-muted)]">{shortDate(u.last_login_at)}</td>
                    <td className="px-4 py-2.5">
                      <div className="flex items-center justify-end gap-1">
                        <button
                          onClick={() => patch(u, { role: u.role === 'admin' ? 'member' : 'admin' })}
                          title={u.role === 'admin' ? 'Make member' : 'Make admin'}
                          className="h-7 px-2 rounded-lg text-[11px] font-medium text-[var(--text-muted)] border border-[var(--border)] hover:text-[var(--text-primary)] hover:bg-[var(--hover)] transition-colors"
                        >
                          {u.role === 'admin' ? 'Make member' : 'Make admin'}
                        </button>
                        <button
                          onClick={() => patch(u, { is_active: !u.is_active })}
                          title={u.is_active ? 'Suspend (blocks sign-in)' : 'Reactivate'}
                          className="h-7 px-2 rounded-lg text-[11px] font-medium text-[var(--text-muted)] border border-[var(--border)] hover:text-[var(--text-primary)] hover:bg-[var(--hover)] transition-colors"
                        >
                          {u.is_active ? 'Suspend' : 'Activate'}
                        </button>
                        <button
                          onClick={() => resetPassword(u)}
                          aria-label={`Reset password for ${u.email}`}
                          title="Reset password (signs them out everywhere)"
                          className="w-7 h-7 rounded-lg flex items-center justify-center text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--hover)] transition-colors border border-[var(--border)]"
                        >
                          <KeyRound className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => remove(u)}
                          disabled={u.id === me?.id}
                          aria-label={`Delete ${u.email}`}
                          title={u.id === me?.id ? 'You cannot delete yourself' : 'Delete account'}
                          className="w-7 h-7 rounded-lg flex items-center justify-center text-[var(--text-muted)] hover:text-[var(--danger)] hover:bg-[var(--hover)] transition-colors border border-[var(--border)] disabled:opacity-30 disabled:pointer-events-none"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
                {users.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-4 py-8 text-center text-[12px] text-[var(--text-faint)]">
                      No accounts yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </ChartCard>

        <ChartCard title="Roles">
          <div className="px-4 pb-4 mt-2 space-y-2 text-[12px] text-[var(--text-muted)]">
            <p><span className="text-[var(--text-primary)]">Admin</span> — full access: providers, users, chat spend.</p>
            <p><span className="text-[var(--text-primary)]">Member</span> — read-only dashboard: overview, logs, models.</p>
          </div>
        </ChartCard>

        {resetModal.open && resetModal.user && (
          <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60" onClick={closeResetModal}>
            <div role="dialog" aria-modal="true" aria-label="Reset password" className="w-full max-w-sm mx-4 p-6 rounded-2xl shadow-2xl" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }} onClick={(e) => e.stopPropagation()}>
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-white">Reset Password</h3>
                <button onClick={closeResetModal} className="text-[var(--text-muted)] hover:text-white transition-colors">
                  <X className="w-5 h-5" />
                </button>
              </div>
              <p className="text-sm text-[#6B7280] mb-4">New password for <strong>{resetModal.user.email}</strong> (signs them out everywhere)</p>
              {resetOk && (
                <p className="flex items-center gap-2 text-[12px] mb-3" style={{ color: 'var(--accent)' }}>
                  <Check className="w-4 h-4" /> Password updated — their sessions were signed out.
                </p>
              )}
              <div className="space-y-3">
                <input
                  type="password"
                  value={resetPw}
                  onChange={(e) => { setResetPw(e.target.value); if (resetErr) setResetErr(''); }}
                  onKeyDown={(e) => e.key === 'Enter' && confirmResetPassword()}
                  placeholder="New password (7+ characters)"
                  className="w-full h-10 px-3 rounded-lg text-sm text-white outline-none font-mono"
                  style={{ background: 'var(--bg-base)', border: `1px solid var(--border)`, color: '#fff' }}
                  autoComplete="new-password"
                />
                <input
                  type="password"
                  value={resetConfirm}
                  onChange={(e) => { setResetConfirm(e.target.value); if (resetErr) setResetErr(''); }}
                  onKeyDown={(e) => e.key === 'Enter' && confirmResetPassword()}
                  placeholder="Confirm new password"
                  className="w-full h-10 px-3 rounded-lg text-sm text-white outline-none font-mono"
                  style={{ background: 'var(--bg-base)', border: `1px solid var(--border)`, color: '#fff' }}
                  autoComplete="new-password"
                />
                {resetErr && <p className="text-xs text-[var(--danger)]">{resetErr}</p>}
              </div>
              <div className="flex gap-2 mt-4">
                <button onClick={closeResetModal} className="flex-1 h-10 rounded-lg text-sm font-medium text-white border border-[var(--border)] hover:bg-[var(--hover)] transition-colors">
                  {resetOk ? 'Done' : 'Cancel'}
                </button>
                <button onClick={confirmResetPassword} disabled={resetBusy || resetOk || resetPw.length < 7} className="flex-1 h-10 rounded-lg text-sm font-medium text-black transition-all disabled:opacity-40 disabled:pointer-events-none" style={{ background: '#00D2A0' }}>
                  {resetOk ? 'Updated' : resetBusy ? 'Resetting…' : 'Reset Password'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </DashPage>
  );
}
