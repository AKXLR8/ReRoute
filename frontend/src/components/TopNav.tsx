import { Link } from 'react-router-dom';
import { useState, useEffect, useRef } from 'react';
import { Menu, X, ArrowRight, ChevronDown } from 'lucide-react';

const nav = [
  { to: '/models', label: 'Models' },
  { href: '/#faq', label: 'FAQs' },
  { to: '/docs', label: 'Docs' },
];

const productItems = [
  { to: '/dashboard', label: 'AI Gateway', desc: 'Route to 40+ models' },
  { to: '/dashboard', label: 'Observability', desc: 'Monitor & trace requests' },
  { to: '/dashboard', label: 'Guardrails', desc: 'PII & content filtering' },
  { to: '/dashboard', label: 'Providers', desc: 'BYOK spend tracking' },
];

export default function TopNav({ onGetKey }: { onGetKey?: () => void }) {
  const [open, setOpen] = useState(false);
  const [productOpen, setProductOpen] = useState(false);
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

  const centerLink = 'text-[14px] font-medium whitespace-nowrap transition-colors text-[#26211F] hover:text-black';

  return (
    <header className="sticky top-0 z-50 h-[82px] flex items-center pointer-events-none">
      <div className="container-x w-full flex justify-center px-3 relative">
        {/* akashml glass pill nav */}
        <div className="w-full max-w-[940px] h-[52px] px-[20px] py-[2px] rounded-[40px] flex items-center justify-between gap-4 pointer-events-auto"
          style={{
            background: 'rgba(255,255,255,0.72)',
            backdropFilter: 'blur(12px)',
            WebkitBackdropFilter: 'blur(12px)',
            boxShadow: '0px 2px 12px 0px rgba(0,0,0,0.10), inset 0.5px 0.5px 0.5px 0 rgba(255,255,255,0.8), inset -0.5px -0.5px 0.5px 0 rgba(255,255,255,0.8)',
            transform: hidden ? 'translateY(-140%)' : 'translateY(0)',
            opacity: hidden ? 0 : 1,
            transition: 'transform 0.3s ease, opacity 0.3s ease',
          }}>
        {/* LEFT: Logo + Wordmark */}
        <Link to="/" className="flex items-center shrink-0">
          <img src="/logo.png" alt="ReRouteAI" className="h-[75px] w-auto object-contain" />
          <span className="relative z-12 -ml-[18px] text-[18px] font-medium tracking-tight leading-none whitespace-nowrap" style={{ color: '#000000', fontFamily: "'Geist', sans-serif" }}>ReRouteAI</span>
        </Link>

        {/* CENTER: Navigation */}
        <nav className="hidden lg:flex items-center flex-1 justify-center gap-7">
          {/* Product dropdown */}
          <div className="relative" onMouseEnter={() => setProductOpen(true)} onMouseLeave={() => setProductOpen(false)}>
            <button onClick={() => setProductOpen(!productOpen)} className={`${centerLink} flex items-center gap-1`} style={{ fontFamily: "'Geist', sans-serif" }}>
              Product <ChevronDown className="w-3 h-3" />
            </button>
            {productOpen && (
              <div className="absolute top-full left-0 pt-2 w-64 z-50">
                <div className="p-2 rounded-2xl border shadow-lg bg-white/95 backdrop-blur-md" style={{ borderColor: 'rgba(0,0,0,0.08)' }}>
                  {productItems.map((item) => (
                    <Link key={item.label} to={item.to}
                      className="flex flex-col gap-0.5 p-2.5 rounded-xl transition-colors hover:bg-[rgba(0,0,0,0.05)]">
                      <span className="text-[13px] font-medium" style={{ color: '#171412', fontFamily: "'Geist', sans-serif" }}>{item.label}</span>
                      <span className="text-[11px]" style={{ color: '#737373', fontFamily: "'Geist', sans-serif" }}>{item.desc}</span>
                    </Link>
                  ))}
                </div>
              </div>
            )}
          </div>

          {nav.map(({ to, href, label }) => {
            return href ? (
              <a key={label} href={href} className={centerLink} style={{ fontFamily: "'Geist', sans-serif" }}>
                {label}
              </a>
            ) : (
              <Link key={to} to={to!} className={centerLink} style={{ fontFamily: "'Geist', sans-serif" }}>
                {label}
              </Link>
            );
          })}
        </nav>

        {/* RIGHT: dark CTA inside the pill */}
        <button
          onClick={onGetKey}
          className="hidden lg:flex h-9 pl-4 pr-3.5 rounded-full text-[13px] font-medium text-white bg-[#171412] hover:bg-[#292524] transition-colors items-center gap-1.5 shrink-0"
          style={{ fontFamily: "'Geist', sans-serif" }}
        >
          Open Dashboard <ArrowRight className="w-4 h-4" />
        </button>

        {/* Mobile menu button — inside the pill so it's always optically centered */}
        <button className="lg:hidden shrink-0 -mr-1.5 p-1 text-[#171412] pointer-events-auto" onClick={() => setOpen(!open)} aria-label="Toggle menu">
          {open ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>
        </div>
      </div>

      {/* Mobile menu */}
      {open && (
        <div className="fixed inset-x-0 top-[82px] bottom-0 border-b z-50 lg:hidden overflow-y-auto bg-[#F5F3EE]/95 backdrop-blur-md" style={{ borderColor: 'rgba(0,0,0,0.08)' }}>
          <nav className="flex flex-col p-4 gap-1">
            <p className="px-4 py-2 text-[10px] font-semibold uppercase tracking-widest text-[#737373]" style={{ fontFamily: "'Geist', sans-serif" }}>Product</p>
            {productItems.map((item) => (
              <Link key={item.label} to={item.to} onClick={() => setOpen(false)}
                className="h-11 px-4 rounded-2xl text-sm font-medium flex items-center text-[#525252] hover:text-[#171412] hover:bg-[rgba(23,20,18,0.05)]" style={{ fontFamily: "'Geist', sans-serif" }}>
                {item.label}
              </Link>
            ))}
            <div className="border-t mt-2 pt-2" style={{ borderColor: 'rgba(0,0,0,0.08)' }}>
              {nav.map(({ to, href, label }) => {
                const cls = `h-11 px-4 rounded-2xl text-sm font-medium flex items-center text-[#525252] hover:text-[#171412] hover:bg-[rgba(23,20,18,0.05)]`;
                return href ? (
                  <a key={label} href={href} onClick={() => setOpen(false)} className={cls}>
                    {label}
                  </a>
                ) : (
                  <Link key={to} to={to!} onClick={() => setOpen(false)} className={cls}>
                    {label}
                  </Link>
                );
              })}
            </div>
            <div className="border-t mt-2 pt-3 flex flex-col gap-2" style={{ borderColor: 'rgba(0,0,0,0.08)' }}>
              <Link to="/dashboard" onClick={() => setOpen(false)}
                className="h-11 px-4 rounded-2xl text-sm font-medium flex items-center text-[#525252]" style={{ fontFamily: "'Geist', sans-serif" }}>
                Sign In
              </Link>
              <button onClick={() => { onGetKey?.(); setOpen(false); }}
                className="h-11 px-4 rounded-full text-sm font-medium text-white flex items-center justify-center gap-2" style={{ background: '#171412', fontFamily: "'Geist', sans-serif" }}>
                Open Dashboard <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </nav>
        </div>
      )}
    </header>
  );
}
