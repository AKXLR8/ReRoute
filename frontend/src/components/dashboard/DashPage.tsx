import { useEffect, useRef, useState, type ReactNode } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { motion } from 'framer-motion';
import { ChevronDown, Settings as SettingsIcon } from 'lucide-react';
import { signOut, visibleNavItems } from '../../lib/nav';

export function TopBar() {
  const loc = useLocation();
  const [acctOpen, setAcctOpen] = useState(false);
  const [hidden, setHidden] = useState(false);
  const lastY = useRef(0);

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
            <Link key={n.to} to={n.to} className={`relative inline-flex h-8 items-center justify-center px-3 sm:px-3.5 rounded-full text-[13px] font-medium whitespace-nowrap transition-colors ${active ? 'text-white' : 'text-[var(--text-muted)] hover:text-white'}`}>
              {active && (
                <motion.span
                  layoutId="dashnav"
                  className="absolute inset-0 rounded-full bg-white/10"
                  transition={{ type: 'spring', stiffness: 380, damping: 32 }}
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
          <button onClick={() => setAcctOpen(!acctOpen)} className="h-9 px-2.5 sm:px-3 rounded-lg flex items-center gap-2 text-[13px] font-medium text-[var(--text-secondary)] hover:bg-[var(--hover)] border border-[var(--border)] transition-colors">
            Account <ChevronDown className="w-3.5 h-3.5" />
          </button>
          {acctOpen && (
            <>
              <div className="fixed inset-0 z-40" onClick={() => setAcctOpen(false)} />
              <div className="absolute right-0 top-full mt-2 w-40 rounded-xl border border-[var(--border)] bg-[#0A0A0A] p-1 shadow-2xl z-50">
                <button onClick={signOut} className="w-full h-9 px-3 rounded-lg text-[13px] text-left text-[var(--text-muted)] hover:bg-[var(--hover)] hover:text-white transition-colors">
                  Sign out
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </header>
  );
}

const RANGES = [7, 30, 90];

export function Segmented({ value, onChange }: { value: number; onChange: (v: number) => void }) {
  return (
    <div className="flex items-center rounded-lg border border-[var(--border)] overflow-hidden shrink-0">
      {RANGES.map((o) => (
        <button
          key={o}
          onClick={() => onChange(o)}
          className={`h-7 px-2 sm:px-3 text-[12px] font-medium transition-colors ${value === o ? 'bg-white/10 text-white' : 'text-[var(--text-muted)] hover:text-[var(--text-secondary)]'}`}
        >
          {o} days
        </button>
      ))}
    </div>
  );
}

/* shared dashboard page: black stage, pill TopBar, big heading + action buttons */
export function DashPage({ title, sub, actions, children }: { title: string; sub?: string; actions?: ReactNode; children: ReactNode }) {
  return (
    <div className="min-h-screen" style={{ background: 'var(--bg-base)' }}>
      <TopBar />
      <div className="max-w-[1440px] mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="flex items-start justify-between gap-4 flex-wrap mb-8">
          <div>
            <h1 className="text-[22px] sm:text-[26px] font-bold tracking-tight text-white">{title}</h1>
            {sub && <p className="text-[14px] text-[var(--text-muted)] mt-1">{sub}</p>}
          </div>
          {actions && <div className="flex items-center gap-2">{actions}</div>}
        </div>
        {children}
        <div className="h-12" />
      </div>
    </div>
  );
}