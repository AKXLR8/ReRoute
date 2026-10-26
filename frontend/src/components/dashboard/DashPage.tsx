import { useEffect, useId, useRef, useState, type ReactNode } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import { ChevronDown, Settings as SettingsIcon } from 'lucide-react';
import { signOut, visibleNavItems } from '../../lib/nav';
import { storedUser } from '../../lib/auth';
import { useEscape } from '../../lib/utils';

export function TopBar() {
  const loc = useLocation();
  const me = storedUser();
  const [acctOpen, setAcctOpen] = useState(false);
  const [hidden, setHidden] = useState(false);
  const lastY = useRef(0);
  const reduce = useReducedMotion();

  useEscape(acctOpen, () => setAcctOpen(false));
  useEffect(() => setAcctOpen(false), [loc.pathname]);

  useEffect(() => {
    const onScroll = () => {
      const y = window.scrollY;
      setHidden(y > lastY.current && y > 120);
      lastY.current = y;
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  return (
    <header
      className="sticky top-0 z-40 h-14 flex items-center gap-2 sm:gap-4 px-4 sm:px-6 border-b border-[var(--border)]"
      style={{
        background: '#000',
        transform: hidden ? 'translateY(-100%)' : 'translateY(0)',
        opacity: hidden ? 0 : 1,
        transition: 'transform 0.3s ease, opacity 0.3s ease',
      }}
    >
      <Link to="/dashboard" className="flex items-center gap-2 shrink-0">
        <img src="/logo.png" alt="" className="h-7 w-auto object-contain" />
        <span className="text-[15px] font-bold text-white tracking-tight hidden sm:block">ReRouteAI</span>
      </Link>
      <nav className="flex-1 min-w-0 flex items-center justify-center gap-1 overflow-x-auto [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden">
        {visibleNavItems().map((n) => {
          const active = loc.pathname === n.to;
          return (
            <Link key={n.to} to={n.to} className={`relative inline-flex h-8 items-center justify-center px-3 sm:px-3.5 rounded-full text-[13px] font-medium whitespace-nowrap transition-colors ${active ? 'text-white' : 'text-[var(--text-muted)] hover:text-white hover:bg-white/[0.04]'}`}>
              {active && (
                <motion.span
                  layoutId="dashnav"
                  className="absolute inset-0 rounded-full bg-white/10"
                  transition={reduce ? { duration: 0 } : { type: 'spring', stiffness: 450, damping: 38, mass: 0.7 }}
                />
              )}
              <span className="relative z-10">{n.label}</span>
            </Link>
          );
        })}
      </nav>
      <div className="flex items-center gap-2 shrink-0">
        <Link to="/dashboard/settings" aria-label="Settings" className="hidden sm:flex w-9 h-9 rounded-lg items-center justify-center text-[var(--text-muted)] hover:text-white hover:bg-[var(--hover)] transition-colors border border-[var(--border)]">
          <SettingsIcon className="w-4 h-4" />
        </Link>
        <div className="relative">
          <button
            onClick={() => setAcctOpen(!acctOpen)}
            aria-haspopup="menu"
            aria-expanded={acctOpen}
            className="h-9 px-2.5 sm:px-3 rounded-lg flex items-center gap-2 text-[13px] font-medium text-[var(--text-secondary)] hover:bg-[var(--hover)] border border-[var(--border)] transition-colors"
          >
            <span className="w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold uppercase shrink-0" style={{ background: 'var(--accent-dim)', color: 'var(--accent)' }}>
              {(me?.email ?? 'A').slice(0, 1)}
            </span>
            <span className="hidden md:inline max-w-[140px] truncate">{me?.email ?? 'Account'}</span>
            <ChevronDown className={`w-3.5 h-3.5 shrink-0 transition-transform duration-200 ${acctOpen ? 'rotate-180' : ''}`} />
          </button>
          {acctOpen && <div className="fixed inset-0 z-40" onClick={() => setAcctOpen(false)} />}
          <AnimatePresence>
            {acctOpen && (
              <motion.div
                role="menu"
                initial={reduce ? false : { opacity: 0, y: -6, scale: 0.97 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: -4, scale: 0.98 }}
                transition={{ duration: reduce ? 0 : 0.16, ease: [0.22, 1, 0.36, 1] }}
                style={{ transformOrigin: 'top right' }}
                className="absolute right-0 top-full mt-2 w-56 rounded-xl border border-[var(--border)] bg-[#0A0A0A] p-1 shadow-2xl z-50"
              >
                <div className="px-3 py-2.5 mb-1 border-b border-[var(--border)]">
                  <p className="text-[12px] font-medium text-[var(--text-primary)] truncate">{me?.email ?? 'Signed in'}</p>
                  <p className="text-[11px] text-[var(--text-muted)] capitalize">{me?.role ?? 'member'}</p>
                </div>
                <Link
                  to="/dashboard/settings"
                  role="menuitem"
                  onClick={() => setAcctOpen(false)}
                  className="w-full h-9 px-3 rounded-lg flex items-center gap-2 text-[13px] text-[var(--text-muted)] hover:bg-[var(--hover)] hover:text-white transition-colors"
                >
                  <SettingsIcon className="w-3.5 h-3.5" /> Settings
                </Link>
                <button
                  role="menuitem"
                  onClick={signOut}
                  className="w-full h-9 px-3 rounded-lg text-[13px] text-left text-[var(--text-muted)] hover:bg-[var(--hover)] hover:text-white transition-colors"
                >
                  Sign out
                </button>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </header>
  );
}

const RANGES = [7, 30, 90];

export function Segmented({ value, onChange }: { value: number; onChange: (v: number) => void }) {
  const id = useId();
  const reduce = useReducedMotion();
  return (
    <div className="relative flex items-center rounded-lg border border-[var(--border)] overflow-hidden shrink-0 bg-[var(--bg-card)]" role="group" aria-label="Date range">
      {RANGES.map((o) => {
        const active = value === o;
        return (
          <button
            key={o}
            onClick={() => onChange(o)}
            aria-pressed={active}
            className={`relative h-7 px-2 sm:px-3 text-[12px] font-medium transition-colors ${active ? 'text-white' : 'text-[var(--text-muted)] hover:text-[var(--text-secondary)]'}`}
          >
            {active && (
              <motion.span
                layoutId={`segmented-${id}`}
                className="absolute inset-0 bg-white/10"
                transition={reduce ? { duration: 0 } : { type: 'spring', stiffness: 500, damping: 40, mass: 0.7 }}
              />
            )}
            <span className="relative z-10">{o} days</span>
          </button>
        );
      })}
    </div>
  );
}

/* shared dashboard page: black stage, pill TopBar, big heading + action buttons */
export function DashPage({ title, sub, actions, children }: { title: string; sub?: string; actions?: ReactNode; children: ReactNode }) {
  const { pathname } = useLocation();
  const reduce = useReducedMotion();

  useEffect(() => {
    document.title = `${title} · ReRouteAI`;
  }, [title]);

  return (
    <div className="min-h-screen" style={{ background: 'var(--bg-base)' }}>
      <motion.div
        key={pathname}
        initial={reduce ? false : { opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: reduce ? 0 : 0.24, ease: [0.22, 1, 0.36, 1] }}
        className="max-w-[1440px] mx-auto px-4 sm:px-6 lg:px-8 py-8"
      >
        <div className="flex items-start justify-between gap-4 flex-wrap mb-8">
          <div>
            <h1 className="text-[22px] sm:text-[26px] font-bold tracking-tight text-white">{title}</h1>
            {sub && <p className="text-[14px] text-[var(--text-muted)] mt-1">{sub}</p>}
          </div>
          {actions && <div className="flex items-center gap-2">{actions}</div>}
        </div>
        {children}
        <div className="h-12" />
      </motion.div>
    </div>
  );
}
