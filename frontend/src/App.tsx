import { lazy, Suspense, useEffect, useState } from 'react';
import { Routes, Route, Navigate, useLocation } from 'react-router-dom';
import TopNav from './components/TopNav';
import { ArrowRight } from 'lucide-react';
import { bootSession, exchangeGithub, storedUser, type SessionUser } from './lib/auth';
import { ToastInitializer } from './components/ToastInitializer';
import Auth from './pages/Auth';

// ponytail: route chunks keep recharts/framer-motion off the login + first paint.
const Landing = lazy(() => import('./pages/Landing'));
const Models = lazy(() => import('./pages/Models'));
const AnalyticsDashboard = lazy(() => import('./pages/AnalyticsDashboard'));
const SettingsPage = lazy(() => import('./pages/Settings'));
const LogsPage = lazy(() => import('./pages/Logs'));
const UsersPage = lazy(() => import('./pages/Users'));
const Docs = lazy(() => import('./pages/Docs'));
const Status = lazy(() => import('./pages/Status'));

/* a route change starts at the top - browser scroll position otherwise leaks across pages */
function ScrollToTop() {
  const { pathname } = useLocation();
  useEffect(() => {
    document.documentElement.scrollTop = 0;
  }, [pathname]);
  return null;
}

const PageFallback = (
  <div className="flex items-center justify-center min-h-screen" style={{ background: 'var(--bg-base)' }}>
    <p className="text-sm text-[#6B7280]">Loading…</p>
  </div>
);

function DashboardShell() {
  // ponytail: paint from the cached session, verify in the background — a refresh
  // shouldn't wait on a network round-trip to show the shell.
  const [user, setUser] = useState<SessionUser | null>(() => storedUser());
  const [checking, setChecking] = useState(() => !storedUser());

  useEffect(() => {
    let alive = true;
    (async () => {
      // GitHub OAuth landed here with a one-time code — trade it for a session first
      const params = new URLSearchParams(window.location.search);
      const ghCode = params.get('gh_code');
      if (ghCode) {
        params.delete('gh_code');
        const qs = params.toString();
        window.history.replaceState({}, '', `${window.location.pathname}${qs ? `?${qs}` : ''}`);
        try { await exchangeGithub(ghCode); } catch { /* stale code → fall through to boot */ }
      }
      bootSession().then((u) => {
        if (!alive) return;
        setUser(u);
        setChecking(false);
      });
    })();
    const onExpired = () => setUser(null);
    window.addEventListener('auth:expired', onExpired);
    return () => {
      alive = false;
      window.removeEventListener('auth:expired', onExpired);
    };
  }, []);

  if (checking) {
    return (
      <div className="flex items-center justify-center min-h-screen" style={{ background: 'var(--bg-base)' }}>
        <p className="text-sm text-[#6B7280]">Loading…</p>
      </div>
    );
  }
  if (!user) return <Auth onLogin={(u) => setUser(u)} />;

  const isAdmin = user.role === 'admin';
  return (
    <Suspense fallback={PageFallback}>
      <Routes>
        <Route index element={<AnalyticsDashboard />} />
        <Route path="models" element={<Models />} />
        <Route path="logs" element={<LogsPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="users" element={isAdmin ? <UsersPage /> : <Navigate to="/dashboard" replace />} />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </Suspense>
  );
}

function PublicPage({ children }: { children: React.ReactNode }) {
  const [getKey, setGetKey] = useState(false);
  return (
    <>
      <TopNav onGetKey={() => setGetKey(true)} />
      {children}
      {getKey && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60" onClick={() => setGetKey(false)}>
          <div className="w-full max-w-sm mx-4 p-6 rounded-2xl shadow-2xl" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }} onClick={(e) => e.stopPropagation()}>
            <h3 className="text-lg font-semibold text-white mb-2">Open the dashboard</h3>
            <p className="text-sm text-[#6B7280] mb-5">Sign in to your account to connect providers and track spend.</p>
            <a href="/dashboard" className="w-full h-10 rounded-xl text-sm font-medium text-black flex items-center justify-center gap-2" style={{ background: '#00D2A0' }}>
              Go to Dashboard <ArrowRight className="w-4 h-4" />
            </a>
          </div>
        </div>
      )}
    </>
  );
}

export default function App() {
  return (
    <>
      <ToastInitializer />
      <ScrollToTop />
      <Suspense fallback={PageFallback}>
        <Routes>
          <Route path="/" element={<PublicPage><Landing /></PublicPage>} />
          <Route path="/models" element={<PublicPage><Models /></PublicPage>} />
          <Route path="/docs" element={<PublicPage><Docs /></PublicPage>} />
          <Route path="/status" element={<PublicPage><Status /></PublicPage>} />
          <Route path="/dashboard/*" element={<DashboardShell />} />
        </Routes>
      </Suspense>
    </>
  );
}
