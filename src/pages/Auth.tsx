import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, Eye, EyeOff, Loader2, ShieldCheck, TriangleAlert } from 'lucide-react';
import { needsSetup, login, register, type SessionUser } from '../lib/auth';

// lucide v1 dropped brand icons; GitHub mark (16px viewbox)
function GithubMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 16 16" className={className} fill="currentColor" aria-hidden="true">
      <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8z" />
    </svg>
  );
}

const FIELD =
  'w-full h-10 px-3 rounded-lg text-sm text-white bg-[var(--bg-base)] border border-[var(--border)] outline-none transition-colors placeholder:text-[#4B5563] focus:border-[var(--purple)]';

export default function Auth({ onLogin }: { onLogin: (u: SessionUser) => void }) {
  const [mode, setMode] = useState<'signin' | 'register'>('signin');
  const [firstRun, setFirstRun] = useState(false); // zero users → force register (no admin key needed)
  const [checking, setChecking] = useState(true);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [showPw, setShowPw] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    needsSetup()
      .then((r) => { if (r.needs_setup) { setMode('register'); setFirstRun(true); } })
      .catch(() => {}) // backend down → normal form, error shows on submit
      .finally(() => setChecking(false));
  }, []);

  const isRegister = mode === 'register';
  const valid =
    /.+@.+\..+/.test(email) &&
    password.length >= 7 &&
    (!isRegister || password === confirm);
  const mismatch = isRegister && confirm.length > 0 && password !== confirm;

  const submit = async () => {
    if (!valid || busy) return;
    setBusy(true);
    setError('');
    try {
      const user = isRegister
        ? await register(email.trim(), password)
        : await login(email.trim(), password);
      onLogin(user);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Sign in failed');
    } finally {
      setBusy(false);
    }
  };

  const switchMode = (m: 'signin' | 'register') => { setMode(m); setError(''); };
  const tabCls = (active: boolean) =>
    `flex-1 h-8 rounded-md text-[13px] font-medium transition-colors ${active ? 'bg-white/10 text-white' : 'text-[var(--text-muted)] hover:text-[var(--text-secondary)]'}`;

  const pwField = (value: string, onChange: (v: string) => void, placeholder: string, autoComplete: string) => (
    <div className="relative">
      <input
        type={showPw ? 'text' : 'password'}
        value={value}
        onChange={(e) => { onChange(e.target.value); if (error) setError(''); }}
        onKeyDown={(e) => e.key === 'Enter' && submit()}
        placeholder={placeholder}
        className={`${FIELD} pr-10`}
        autoComplete={autoComplete}
      />
      <button
        type="button"
        onClick={() => setShowPw(!showPw)}
        tabIndex={-1}
        aria-label={showPw ? 'Hide password' : 'Show password'}
        className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[var(--text-faint)] hover:text-[var(--text-secondary)] transition-colors"
      >
        {showPw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
      </button>
    </div>
  );

  return (
    <div className="relative flex items-center justify-center min-h-screen px-4 py-10" style={{ background: 'var(--bg-base)' }}>
      <div className="fixed inset-0 opacity-[0.035] pointer-events-none" style={{
        backgroundImage: 'linear-gradient(rgba(255,255,255,0.07) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.07) 1px, transparent 1px)',
        backgroundSize: '56px 56px',
      }} />
      <div className="fixed left-1/2 -translate-x-1/2 -top-40 w-[620px] h-[520px] rounded-full opacity-[0.10] blur-3xl pointer-events-none"
        style={{ background: 'radial-gradient(circle, var(--purple), transparent 70%)' }} />

      <div className="relative z-10 w-full max-w-[400px]">
        <Link to="/" className="flex flex-col items-center gap-3 mb-6 group">
          <img src="/logo.png" alt="ReRouteAI" className="h-16 w-auto object-contain" />
          <div className="text-center">
            <div className="text-[15px] font-bold text-white tracking-tight transition-opacity group-hover:opacity-80">ReRouteAI</div>
            <div className="text-[13px] text-[var(--text-muted)] mt-0.5">One API. Every provider.</div>
          </div>
        </Link>

        <div className="rounded-2xl p-6 sm:p-7" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
          {!checking && !firstRun && (
            <div className="flex items-center gap-1 p-1 rounded-lg mb-5" style={{ background: 'var(--bg-base)', border: '1px solid var(--border)' }}>
              <button type="button" onClick={() => switchMode('signin')} className={tabCls(mode === 'signin')}>Sign in</button>
              <button type="button" onClick={() => switchMode('register')} className={tabCls(mode === 'register')}>Create account</button>
            </div>
          )}

          <div className="mb-5">
            <h1 className="text-[19px] font-semibold text-white tracking-tight">
              {firstRun ? 'Create your admin account' : isRegister ? 'Create your account' : 'Welcome back'}
            </h1>
            <p className="text-[13px] text-[var(--text-muted)] mt-1">
              {firstRun
                ? 'Zero-user setup — the first account becomes the admin'
                : isRegister
                  ? 'Choose an email and password to get started'
                  : 'Sign in to your dashboard'}
            </p>
          </div>

          {firstRun && (
            <div className="flex items-start gap-2 p-2.5 mb-4 rounded-lg text-[12px] leading-relaxed"
              style={{ background: 'var(--purple-dim)', border: '1px solid rgba(139,92,246,0.3)', color: '#C4B5FD' }}>
              <ShieldCheck className="w-3.5 h-3.5 mt-px shrink-0" />
              <span>This account will own the gateway — pick the password carefully.</span>
            </div>
          )}

          <div className="space-y-3.5">
            <label className="block">
              <span className="block text-[12px] font-medium text-[var(--text-secondary)] mb-1.5">Email</span>
              <input
                type="email"
                value={email}
                onChange={(e) => { setEmail(e.target.value); if (error) setError(''); }}
                onKeyDown={(e) => e.key === 'Enter' && submit()}
                placeholder="you@company.com"
                className={FIELD}
                autoComplete="email"
              />
            </label>

            <label className="block">
              <span className="flex items-center justify-between mb-1.5">
                <span className="text-[12px] font-medium text-[var(--text-secondary)]">Password</span>
                {isRegister && <span className="text-[11px] text-[var(--text-faint)]">7+ characters</span>}
              </span>
              {pwField(password, setPassword, isRegister ? 'Create a password' : 'Enter your password', isRegister ? 'new-password' : 'current-password')}
            </label>

            {isRegister && (
              <label className="block">
                <span className="block text-[12px] font-medium text-[var(--text-secondary)] mb-1.5">Confirm password</span>
                {pwField(confirm, setConfirm, 'Repeat your password', 'new-password')}
                {mismatch && <span className="block text-[11.5px] mt-1.5" style={{ color: 'var(--danger)' }}>Passwords don't match</span>}
              </label>
            )}

            {error && (
              <p role="alert" className="flex items-start gap-2 p-2.5 rounded-lg text-[12.5px] leading-relaxed"
                style={{ background: 'var(--danger-dim)', border: '1px solid rgba(229,83,75,0.35)', color: '#FCA5A5' }}>
                <TriangleAlert className="w-3.5 h-3.5 mt-px shrink-0" />
                <span>{error}</span>
              </p>
            )}
          </div>

          <button
            onClick={submit}
            disabled={!valid || busy || checking}
            className="w-full h-10 mt-4 rounded-lg text-sm font-semibold text-white flex items-center justify-center gap-2 transition-all disabled:opacity-40 disabled:pointer-events-none active:scale-[0.98] hover:opacity-90"
            style={{ background: 'var(--purple)' }}
          >
            {busy ? (
              <><Loader2 className="w-4 h-4 animate-spin" /> {isRegister ? 'Creating account…' : 'Signing in…'}</>
            ) : checking ? 'Checking…' : (
              <>{isRegister ? 'Create account' : 'Sign in'} <ArrowRight className="w-4 h-4" /></>
            )}
          </button>

          {!checking && (
            <div className="mt-4 space-y-3">
              <div className="flex items-center gap-3">
                <div className="h-px flex-1" style={{ background: 'var(--border)' }} />
                <span className="text-[11px] text-[var(--text-faint)]">or</span>
                <div className="h-px flex-1" style={{ background: 'var(--border)' }} />
              </div>
              <a
                href="/auth/github/authorize"
                className="w-full h-10 rounded-lg text-sm font-medium text-white transition-colors flex items-center justify-center gap-2 hover:bg-[var(--hover)]"
                style={{ background: 'var(--bg-base)', border: '1px solid var(--border)' }}
              >
                <GithubMark className="w-4 h-4" /> Continue with GitHub
              </a>
            </div>
          )}
        </div>

        <p className="text-center text-[11px] text-[var(--text-faint)] mt-5">v0.1.0</p>
      </div>
    </div>
  );
}
