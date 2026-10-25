import { useState, useRef } from 'react';
import { Link } from 'react-router-dom';
import { motion, useInView, AnimatePresence, type Variants } from 'framer-motion';
import {
  ArrowRight, Code, Copy as CopyIcon, ChevronDown,
} from 'lucide-react';
import {
  TbShieldCheck, TbCpu, TbCheck,
} from 'react-icons/tb';
import { brandLogo, filteredLogo } from '../lib/logos';
import { TextEffect } from '../components/motion-primitives/text-effect';
import TechText from '../components/TechText';
import FadeContent from '../components/FadeContent';
import { AnimatedGroup } from '../components/motion-primitives/animated-group';

/* ─── Design Tokens ─── */
const C = 'container-x' as const;
const Y = 'py-[80px] lg:py-[112px]' as const;

/* akashml re-skin: warm near-black canvas, monochrome neutrals, hairline borders */
const INK = '#F5F5F5';
const MUTED = '#A3A3A3';
const FAINT = '#6B6B6B';
const GREEN = '#D6D3CF';
const LINE = 'rgba(255,255,255,0.10)';
const CARD = '#1F1A19';
const TILE = '#26211F';
const BTN = '#EDEBE8';

const fadeUp: Variants = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.5, ease: [0.22, 1, 0.36, 1] as const } },
};

function useAnimateInView(threshold = 0.15) {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, amount: threshold });
  return { ref, isInView };
}

const integrations: { name: string; color: string; slug?: string }[] = [
  { name: 'OpenAI', color: '#22C55E', slug: 'openai' },
  { name: 'Anthropic', color: '#A855F7', slug: 'anthropic' },
  { name: 'Google Gemini', color: '#3B82F6', slug: 'googlegemini' },
  { name: 'Groq', color: '#EAB308', slug: 'groq' },
  { name: 'Mercury', color: '#EC4899', slug: 'mercury' },
  { name: 'Ollama', color: '#06B6D4', slug: 'ollama' },
];

const faqs = [
  { q: 'What is ReRouteAI?', a: 'An OpenAI-compatible proxy that sits between your app and LLM providers. One endpoint — it handles routing, caching, failover, and logging so you write fewer one-off integrations.' },
  { q: 'How does the semantic cache work?', a: 'Embeddings compare incoming prompts to previous ones. Close enough matches get a cached response back without hitting the model. You control the similarity threshold and TTL.' },
  { q: 'Which providers do you support?', a: 'OpenAI, Anthropic, Google Gemini, Groq, Mercury, Ollama — and any OpenAI-compatible endpoint.' },
  { q: 'Why did you build this?', a: 'As a side project to learn how LLM gateways work under the hood — routing, caching, rate limiting, guardrails — and to track my own AI spend across providers in one place.' },
];

const codeSnippet = `import OpenAI from 'openai';

// point the OpenAI SDK at the gateway — nothing else changes
const client = new OpenAI({
  apiKey: process.env.FGW_API_KEY,
  baseURL: 'http://localhost:8000/v1',
});

const response = await client.chat.completions.create({
  model: 'mercury-2',
  messages: [{ role: 'user', content: 'Hello!' }],
});

console.log(response.choices[0].message.content);`;

/* ═══════════ Shared bits ═══════════ */
function Eyebrow({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-[11px] font-medium tracking-[0.1em] uppercase mb-[12px]" style={{ color: '#A3A3A3', fontFamily: "'Geist', sans-serif" }}>
      {children}
    </p>
  );
}

/* ═══════════ HERO ═══════════ */
function HeroSection() {
  const { ref, isInView } = useAnimateInView(0.1);

  return (
    <section ref={ref} className="relative overflow-hidden">
      {/* single full-bleed hero art (akashml style) — natural ratio, no stretch */}
      <div className="absolute inset-0 flex items-center justify-center">
        <img src="/new.png" alt="" loading="eager" className="w-full h-auto object-contain opacity-50" />
      </div>
      {/* cinematic vignette: dark corners around the image */}
      <div className="absolute inset-0 pointer-events-none" style={{ background: 'radial-gradient(ellipse 130% 100% at 50% 46%, transparent 52%, rgba(0,0,0,0.92) 100%)' }} />
      <div className={`${C} w-full pt-[56px] lg:pt-[72px] pb-[80px] relative z-10 text-center`}>
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={isInView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.6, delay: 0.2 }}
          className="relative z-10 mt-[12px] px-4"
        >
          <FadeContent delay={100} duration={800} blur className="relative z-10">
            <h1 className="leading-[0.95]">
              <div className="w-full relative h-[160px] sm:h-[200px] lg:h-[240px]">
                <TechText text="Know Your AI" fontWeight={600} fontSize={150} reveal="letter" dashLength={4} dashGap={2} specks={15} />
              </div>
            </h1>
          </FadeContent>
          <FadeContent delay={450} duration={800} blur>
            <p className="mx-auto max-w-[640px] leading-[1.5]" style={{ color: '#FFFFFF', fontSize: 'clamp(1rem, 1.6vw, 1.25rem)', fontFamily: "'Geist', sans-serif", fontWeight: 600, textShadow: '0 2px 24px rgba(0,0,0,0.6)' }}>
              Know what every request costs you — tokens, latency and spend across every provider, in one dashboard.
            </p>
          </FadeContent>
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-center gap-[12px] mt-[32px]">
            <Link to="/dashboard" className="h-[48px] px-[28px] text-[14px] font-semibold text-[#171412] transition-transform hover:scale-[1.02] active:scale-[0.98] flex items-center justify-center gap-2 rounded-full" style={{ background: '#FFFFFF', fontFamily: "'Geist', sans-serif" }}>
              Get Started <ArrowRight className="w-4 h-4" />
            </Link>
            <Link to="/docs" className="h-[48px] px-[28px] text-[14px] font-semibold transition-colors flex items-center justify-center gap-2 rounded-full" style={{ color: '#FFFFFF', background: 'rgba(255,255,255,0.08)', border: '1px solid rgba(255,255,255,0.16)', fontFamily: "'Geist', sans-serif", backdropFilter: 'blur(8px)' }}>
              <Code className="w-4 h-4" /> View Docs
            </Link>
          </div>
        </motion.div>
      </div>
    </section>
  );
}

/* ═══════════ FEATURES ═══════════ */

/* ponytail: card chrome shared by all 5 feature panels; visual area ~65% */
function FeaturePanel({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`sticker overflow-hidden flex flex-col h-full ${className ?? ''}`}>
      <div className="relative m-[10px] mb-0 rounded-[10px] overflow-hidden shrink-0"
        style={{ background: '#171412', border: '1px solid rgba(255,255,255,0.08)' }}>
        <div className="absolute inset-0 noise opacity-[0.5] mix-blend-overlay pointer-events-none" />
        <div className="absolute inset-y-0 left-0 w-px bg-white/10 pointer-events-none" />
        {children}
      </div>
    </div>
  );
}

function FeatBody({ title, desc }: { title: string; desc: string }) {
  return (
    <div className="p-[18px] lg:p-[20px] flex flex-col gap-[6px] flex-1">
      <h3 className="text-[16px] lg:text-[17px] font-semibold leading-snug" style={{ color: INK, fontFamily: "'Geist', sans-serif" }}>{title}</h3>
      <p className="text-[13.5px] lg:text-[14px] leading-[1.65]" style={{ color: MUTED, fontFamily: "'Geist', sans-serif", fontWeight: 400 }}>{desc}</p>
    </div>
  );
}

function RateLimitVisual() {
  const limits = [
    { name: 'rpm', label: '38 / 60 req/min', pct: 63 },
    { name: 'tpm', label: '42k / 100k tok/min', pct: 42 },
    { name: 'concurrent', label: '4 / 10 in flight', pct: 40 },
  ];
  return (
    <div className="relative h-[210px] lg:h-[240px] p-[16px] flex flex-col gap-[12px]">
      {limits.map((t) => (
        <div key={t.name}>
          <div className="flex items-center justify-between mb-[6px] px-1">
            <span className="text-[10px] font-medium" style={{ color: '#C9C6C2', fontFamily: "JetBrains Mono, monospace" }}>{t.name}</span>
            <span className="text-[10px]" style={{ color: FAINT, fontFamily: "JetBrains Mono, monospace" }}>{t.label}</span>
          </div>
          <div className="h-[8px] rounded-full" style={{ background: 'rgba(255,255,255,0.07)' }}>
            <div className="h-full rounded-full" style={{ width: `${t.pct}%`, background: '#D6D3CF' }} />
          </div>
        </div>
      ))}
      <span className="mt-auto text-[10px] px-1" style={{ color: FAINT, fontFamily: "JetBrains Mono, monospace" }}>global limits · enforced on every request</span>
    </div>
  );
}

function ModelUsageVisual() {
  const rows = [
    { name: 'gpt-4o', req: '12.4k', cost: '$8.20' },
    { name: 'mercury-2', req: '3.1k', cost: '$1.44' },
    { name: 'llama-3.3-70b', req: '0.4k', cost: '$0.09' },
  ];
  return (
    <div className="relative h-[200px] p-[16px] flex flex-col gap-[10px]">
      {rows.map((k) => (
        <div key={k.name} className="flex items-center justify-between px-3 py-2 rounded-lg" style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.07)' }}>
          <span className="text-[11px] font-medium" style={{ color: '#EDEBE8', fontFamily: "JetBrains Mono, monospace" }}>{k.name}</span>
          <div className="flex items-center gap-[8px]">
            <span className="text-[9px] px-1.5 py-0.5 rounded" style={{ background: 'rgba(255,255,255,0.10)', color: '#EDEBE8', fontFamily: "JetBrains Mono, monospace" }}>{k.req} req</span>
            <span className="text-[9px]" style={{ color: '#D6D3CF', fontFamily: "JetBrains Mono, monospace" }}>{k.cost}</span>
          </div>
        </div>
      ))}
    </div>
  );
}

function GuardrailVisual() {
  const rows = [
    { rule: 'secrets', detail: 'sk-… key in prompt', action: 'blocked' },
    { rule: 'pii', detail: 'email address', action: 'blocked' },
    { rule: 'injection', detail: 'ignore previous…', action: 'blocked' },
    { rule: 'jailbreak', detail: 'DAN-style request', action: 'blocked' },
  ];
  return (
    <div className="relative h-[200px] p-[16px] flex flex-col gap-[10px]">
      {rows.map((r) => (
        <div key={r.rule} className="flex items-center justify-between px-3 py-2 rounded-lg" style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.07)' }}>
          <span className="text-[11px] font-medium" style={{ color: '#EDEBE8', fontFamily: "JetBrains Mono, monospace" }}>{r.rule}</span>
          <div className="flex items-center gap-[8px]">
            <span className="text-[9px]" style={{ color: FAINT, fontFamily: "JetBrains Mono, monospace" }}>{r.detail}</span>
            <span className="text-[9px] px-1.5 py-0.5 rounded" style={{ background: 'rgba(255,255,255,0.10)', color: '#D6D3CF', fontFamily: "JetBrains Mono, monospace" }}>{r.action}</span>
          </div>
        </div>
      ))}
    </div>
  );
}

function CacheVisual() {
  const rows = [
    { prompt: 'Summarize this quarter\u2019s churn…', match: '98% match', hit: true },
    { prompt: 'Explain how rate limits work…', match: '96% match', hit: true },
    { prompt: 'Write a SQL join for orders…', match: 'no match', hit: false },
  ];
  return (
    <div className="relative h-[200px] p-[16px] flex flex-col gap-[8px]">
      <span className="text-[10px] px-1" style={{ color: FAINT, fontFamily: "JetBrains Mono, monospace" }}>semantic cache</span>
      {rows.map((r) => (
        <div key={r.prompt} className="flex items-center justify-between gap-2 px-3 py-2 rounded-lg" style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.07)' }}>
          <span className="text-[10px] truncate" style={{ color: '#C9C6C2', fontFamily: "JetBrains Mono, monospace" }}>{r.prompt}</span>
          <div className="flex items-center gap-[8px] shrink-0">
            <span className="text-[9px]" style={{ color: FAINT, fontFamily: "JetBrains Mono, monospace" }}>{r.match}</span>
            <span className="text-[9px] px-1.5 py-0.5 rounded" style={{ background: r.hit ? 'rgba(255,255,255,0.10)' : 'rgba(255,255,255,0.04)', color: r.hit ? '#D6D3CF' : FAINT, fontFamily: "JetBrains Mono, monospace" }}>{r.hit ? 'cached' : 'live'}</span>
          </div>
        </div>
      ))}
      <span className="mt-auto text-[10px] px-1" style={{ color: FAINT, fontFamily: "JetBrains Mono, monospace" }}>hit rate on the dashboard</span>
    </div>
  );
}

  const panels = [
  { key: 'usage', span: 'lg:col-span-3', visual: <ModelUsageVisual />, title: 'Usage Analytics', desc: 'Tokens, cost and latency per model — every request logged, live in the dashboard.' },
  { key: 'limits', span: 'lg:col-span-3', visual: <RateLimitVisual />, title: 'Rate Limits', desc: 'RPM, tokens-per-minute and concurrency caps enforced on every request, so one runaway loop can\'t take the gateway down.' },
  { key: 'cache', span: 'lg:col-span-3', visual: <CacheVisual />, title: 'Semantic Cache', desc: 'Similar prompts get answered from cache without hitting the model — hit rate tracked on the dashboard.' },
  { key: 'guardrails', span: 'lg:col-span-3', visual: <GuardrailVisual />, title: 'Guardrails', desc: 'Secrets, PII, prompt injection and jailbreak attempts blocked before they reach the provider.' },
];

function FeaturesSection() {
  const { ref, isInView } = useAnimateInView();

  return (
    <section id="features" ref={ref} className={Y}>
      <div className={`${C} overflow-hidden`}>
        <motion.div variants={fadeUp} initial="hidden" animate={isInView ? 'visible' : 'hidden'} className="max-w-[640px] mb-[40px]">
          <Eyebrow>Features</Eyebrow>
          <h2 className="font-editorial font-light tracking-[-0.02em] leading-[1.0]" style={{ color: INK, fontSize: 'clamp(2rem, 4vw, 3rem)' }}>The boring parts, handled</h2>
          <p className="mt-[16px] leading-[1.6] max-w-[520px]" style={{ color: MUTED, fontSize: 'clamp(0.95rem, 1.3vw, 1.1rem)', fontFamily: "'Geist', sans-serif", fontWeight: 400 }}>Usage, rate limits, cache and guardrails — every request accounted for, in one log you can read.</p>
        </motion.div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-6 gap-[14px]">
          {panels.map((p, i) => (
            <motion.div
              key={p.key}
              variants={fadeUp}
              initial="hidden"
              animate={isInView ? 'visible' : 'hidden'}
              transition={{ delay: 0.08 * i }}
              className={`${p.span}`}
            >
              <FeaturePanel>
                {p.visual}
                <FeatBody title={p.title} desc={p.desc} />
              </FeaturePanel>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ═══════════ WHY ═══════════ */
function WhySection() {
  const { ref, isInView } = useAnimateInView();

  return (
    <section ref={ref} className={Y}>
      <div className={C}>
        <motion.div variants={fadeUp} initial="hidden" animate={isInView ? 'visible' : 'hidden'} className="max-w-[720px]">
          <Eyebrow>Why I built it</Eyebrow>
          <h2 className="font-editorial font-light tracking-[-0.02em] leading-[1.0]" style={{ color: INK, fontSize: 'clamp(2rem, 4vw, 3rem)' }}>To know what my AI is actually doing</h2>
          <p className="mt-[16px] leading-[1.7]" style={{ color: MUTED, fontSize: 'clamp(0.95rem, 1.3vw, 1.1rem)', fontFamily: "'Geist', sans-serif", fontWeight: 400 }}>
            I built this side project to learn how LLM gateways work — routing, caching, rate limits, guardrails —
            and to answer one blunt question: where does my AI spend actually go? Every request lands in one log:
            tokens, cost, latency, cache hits. No guesswork, just a log you can read.
          </p>
        </motion.div>
      </div>
    </section>
  );
}

/* ═══════════ PRODUCT SHOWCASE ═══════════ */
function ProductShowcase() {
  const sections = [
    { title: 'Bring your own key (BYOK)', desc: "Connect your OpenAI, Anthropic or Groq key from the dashboard. It stays encrypted and masked — and every request through it gets the same tracking: tokens, cost, latency and cache hits.", features: ['Encrypted at rest, masked in the UI', 'Your key, your provider bill', 'Full usage tracking per request', 'Revoke or rotate any time'], icon: <TbShieldCheck className="w-5 h-5" strokeWidth={2.25} /> },
  ];

  return (
    <section id="gateway" className={Y} style={{ /* ponytail: no section borders — video BG */ }}>
      <div className={`${C} space-y-[72px] lg:space-y-[96px]`}>
        {sections.map((section, i) => {
          const isReversed = i % 2 !== 0;

          return (
            <div key={section.title} className="grid lg:grid-cols-2 gap-[40px] lg:gap-[64px] items-center">
              <motion.div variants={fadeUp} initial="hidden" whileInView="visible" viewport={{ once: true, amount: 0.15 }} className={isReversed ? 'lg:order-2' : ''}>
                <div className="w-[40px] h-[40px] rounded-lg flex items-center justify-center mb-[16px] text-[#F5F5F5]" style={{ background: 'rgba(255,255,255,0.08)' }}>{section.icon}</div>
                <h2 className="font-editorial font-light tracking-[-0.02em] leading-[1.0] mb-[12px]" style={{ color: INK, fontSize: 'clamp(1.8rem, 3vw, 2.4rem)' }}>{section.title}</h2>
                <p className="leading-[1.6] mb-[20px] max-w-[520px]" style={{ color: MUTED, fontSize: 'clamp(0.9rem, 1.2vw, 1rem)', fontFamily: "'Geist', sans-serif", fontWeight: 400 }}>{section.desc}</p>
                <div className="space-y-[10px]">
                  {section.features.map((f) => (
                    <div key={f} className="flex items-center gap-[10px] text-[15px]" style={{ color: INK }}>
                      <TbCheck className="w-4 h-4 shrink-0" style={{ color: '#D6D3CF' }} strokeWidth={3} />
                      {f}
                    </div>
                  ))}
                </div>
              </motion.div>

              <motion.div variants={fadeUp} initial="hidden" whileInView="visible" viewport={{ once: true, amount: 0.15 }} transition={{ delay: 0.1 }} className={`relative ${isReversed ? 'lg:order-1' : ''}`}>
                {i === 0 && (
                  /* BYOK — connected provider keys */
                  <div className="rounded-xl overflow-hidden" style={{ background: CARD, border: `1px solid ${LINE}`, boxShadow: '0 16px 48px rgba(0,0,0,0.5)' }}>
                    <div className="flex items-center justify-between px-[16px] py-[10px]" style={{ borderBottom: `1px solid ${LINE}` }}>
                      <span className="text-[12px] font-medium" style={{ color: INK }}>Provider Keys</span>
                      <span className="text-[11px] font-medium" style={{ color: '#8B8B8B' }}>● encrypted</span>
                    </div>
                    <div className="p-[16px]">
                      <div className="space-y-[8px]">
                        {[
                          { provider: 'openai', masked: 'sk-...a3f9', state: 'connected' },
                          { provider: 'anthropic', masked: 'sk-...9c21', state: 'connected' },
                          { provider: 'groq', masked: 'gsk_...7d4e', state: 'connected' },
                          { provider: 'gemini', masked: '', state: 'connect' },
                        ].map((k) => (
                          <motion.div
                            key={k.provider}
                            initial={{ opacity: 0, x: -12 }}
                            whileInView={{ opacity: 1, x: 0 }}
                            viewport={{ once: true, amount: 0.15 }}
                            transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
                            className="flex items-center gap-[12px] px-[12px] py-[10px] rounded-lg"
                            style={{ background: 'rgba(255,255,255,0.02)' }}
                          >
                            <span className="w-[6px] h-[6px] rounded-full shrink-0" style={{ background: k.state === 'connected' ? '#8B8B8B' : '#4B5563' }} />
                            <span className="text-[13px] font-mono flex-1" style={{ color: INK }}>{k.provider}</span>
                            <span className="text-[12px] font-mono shrink-0" style={{ color: MUTED }}>{k.masked || '—'}</span>
                            <span className="text-[11px] px-[8px] py-[2px] rounded-full font-medium shrink-0" style={k.state === 'connected' ? { background: 'rgba(255,255,255,0.08)', color: '#D6D3CF' } : { background: 'rgba(255,255,255,0.05)', color: FAINT }}>{k.state}</span>
                          </motion.div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
              </motion.div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

/* ═══════════ INTEGRATIONS ═══════════ */
function IntegrationsSection() {
  const { ref, isInView } = useAnimateInView();

  return (
    <section ref={ref} className={Y} style={{ /* ponytail: no section borders — video BG */ }}>
      <div className={`${C}`}>
        <motion.div variants={fadeUp} initial="hidden" animate={isInView ? 'visible' : 'hidden'} className="max-w-[640px] mb-[40px]">
          <Eyebrow>Integrations</Eyebrow>
          <h2 className="font-editorial font-light tracking-[-0.02em] leading-[1.0]" style={{ color: INK, fontSize: 'clamp(2rem, 4vw, 3rem)' }}>One API, every provider</h2>
          <p className="mt-[16px] leading-[1.6]" style={{ color: MUTED, fontSize: 'clamp(0.95rem, 1.3vw, 1.1rem)', fontFamily: "'Geist', sans-serif", fontWeight: 400 }}>Swap providers by changing a string. Your code doesn't move.</p>
        </motion.div>

        <AnimatedGroup preset="fade" className="flex items-center justify-center gap-x-[56px] sm:gap-x-[80px] gap-y-[40px] flex-wrap">
          {integrations.map((intg) => (
            <div key={intg.name} className="flex flex-col items-center gap-[12px] cursor-default opacity-60 hover:opacity-100 transition-opacity duration-300">
              {intg.slug && brandLogo[intg.slug] ? (
                <img
                  src={brandLogo[intg.slug]}
                  alt={`${intg.name} logo`}
                  loading="lazy"
                  className={`${filteredLogo.has(intg.slug) ? 'logo-white ' : ''}h-[32px] w-auto max-w-[120px] object-contain`}
                />
              ) : (
                <TbCpu className="w-8 h-8" strokeWidth={2} style={{ color: intg.color }} />
              )}
              <span className="text-[14px]" style={{ color: MUTED, fontFamily: "'Geist', sans-serif", fontWeight: 400 }}>{intg.name}</span>
            </div>
          ))}
        </AnimatedGroup>
      </div>
    </section>
  );
}

/* ═══════════ DEVELOPER EXPERIENCE ═══════════ */
function DeveloperExperience() {
  const { ref, isInView } = useAnimateInView();
  const [copied, setCopied] = useState(false);

  const copyCode = () => {
    navigator.clipboard.writeText(codeSnippet);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <section ref={ref} className={Y} style={{ /* ponytail: no section borders — video BG */ }}>
      <div className={`${C}`}>
        <div className="grid lg:grid-cols-[1.05fr_0.95fr] gap-[40px] lg:gap-[64px] items-center">
          <motion.div variants={fadeUp} initial="hidden" animate={isInView ? 'visible' : 'hidden'}>
            <Eyebrow>Developer Experience</Eyebrow>
            <h2 className="font-editorial font-light tracking-[-0.02em] leading-[1.0] mb-[12px]" style={{ color: INK, fontSize: 'clamp(2rem, 4vw, 3rem)' }}>Drop-in, not rip-out</h2>
            <p className="leading-[1.6] mb-[20px] max-w-[520px]" style={{ color: MUTED, fontSize: 'clamp(0.95rem, 1.3vw, 1.1rem)', fontFamily: "'Geist', sans-serif", fontWeight: 400 }}>Works with OpenAI SDK, LangChain, or any HTTP client. Swap one import and you're routing through ReRouteAI.</p>
            <div className="space-y-[10px]">
              {['OpenAI SDK compatible', 'One baseURL, no rewrite', 'No provider lock-in'].map((f) => (
                <div key={f} className="flex items-center gap-[10px] text-[15px]" style={{ color: INK }}>
                  <TbCheck className="w-4 h-4 shrink-0" style={{ color: GREEN }} strokeWidth={3} />
                  {f}
                </div>
              ))}
            </div>
          </motion.div>

          <motion.div variants={fadeUp} initial="hidden" animate={isInView ? 'visible' : 'hidden'}>
            <div className="rounded-xl overflow-hidden flex flex-col" style={{ background: '#171412', border: `1px solid ${LINE}` }}>
              <div className="flex items-center justify-between px-[16px] py-[10px] shrink-0" style={{ borderBottom: `1px solid ${LINE}` }}>
                <div className="flex items-center gap-[8px]">
                  <div className="flex gap-[6px]">
                    <span className="w-[10px] h-[10px] rounded-full bg-[#6B6B6B]" />
                    <span className="w-[10px] h-[10px] rounded-full bg-[#555]" />
                    <span className="w-[10px] h-[10px] rounded-full bg-[#777]" />
                  </div>
                  <span className="text-[12px] ml-[8px] font-mono" style={{ color: FAINT }}>app.ts</span>
                </div>
                <button onClick={copyCode} className="p-[6px] rounded-md hover:bg-white/10 transition-colors self-start" style={{ color: FAINT }} aria-label="Copy code">
                  {copied ? <TbCheck className="w-[14px] h-[14px] text-[#D6D3CF]" /> : <CopyIcon className="w-[14px] h-[14px]" />}
                </button>
              </div>
              <pre className="p-[22px] text-[13px] leading-[1.7] overflow-x-auto font-mono flex-1">
                <code style={{ color: '#F5F5F5' }}>{codeSnippet}</code>
              </pre>
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  );
}

/* ═══════════ FAQ ═══════════ */
function FAQSection() {
  const { ref, isInView } = useAnimateInView();
  const [openIndex, setOpenIndex] = useState<number | null>(null);

  return (
    <section id="faq" ref={ref} className={Y} style={{ /* ponytail: no section borders — video BG */ }}>
      <div className="max-w-[768px] mx-auto px-4 sm:px-6 lg:px-8">
        <motion.div variants={fadeUp} initial="hidden" animate={isInView ? 'visible' : 'hidden'} className="mb-[32px]">
          <Eyebrow>FAQ</Eyebrow>
          <h2 className="font-editorial font-light tracking-[-0.02em] leading-[1.0]" style={{ color: INK, fontSize: 'clamp(2rem, 4vw, 3rem)' }}>Frequently asked questions</h2>
        </motion.div>

        <div style={{ /* ponytail: no section borders — video BG */ }}>
          {faqs.map((faq, i) => (
            <motion.div key={i} variants={fadeUp} initial="hidden" animate={isInView ? 'visible' : 'hidden'} style={{ borderBottom: `1px solid ${LINE}` }}>
              <button onClick={() => setOpenIndex(openIndex === i ? null : i)} className="w-full py-[20px] flex items-center gap-[16px] text-left">
                <span className="text-[15px] font-semibold flex-1" style={{ color: INK }}>{faq.q}</span>
                <ChevronDown className={`w-[18px] h-[18px] transition-transform shrink-0 ${openIndex === i ? 'rotate-180' : ''}`} style={{ color: FAINT }} strokeWidth={2.5} />
              </button>
              <AnimatePresence>
                {openIndex === i && (
                  <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.2 }}>
                    <div className="pb-[20px] pr-[40px] text-[15px] leading-relaxed" style={{ color: MUTED }}>{faq.a}</div>
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ═══════════ FINAL CTA ═══════════ */
function FinalCTA() {
  const { ref, isInView } = useAnimateInView();

  return (
    <section ref={ref} className={Y} style={{ /* ponytail: no section borders — video BG */ }}>
      <div className={`${C}`}>
          <motion.div
            variants={fadeUp} initial="hidden" animate={isInView ? 'visible' : 'hidden'}
            className="max-w-[880px] mx-auto px-6 sm:px-12 py-[56px] sm:py-[72px] rounded-2xl text-center"
            style={{ background: TILE, border: `1px solid ${LINE}`, boxShadow: '0 16px 64px rgba(0,0,0,0.6)' }}
          >
            <TextEffect
              per="word"
              preset="fade-in-blur"
              delay={0.1}
              className="font-editorial font-light tracking-[-0.025em] leading-[1.0] mb-[12px]"
              style={{ color: INK, fontSize: 'clamp(2rem, 4.5vw, 3.2rem)' }}
              as="h2"
            >
              Ship the routing, not the plumbing
            </TextEffect>
            <p className="mb-[28px] max-w-[520px] mx-auto" style={{ color: MUTED, fontSize: 'clamp(0.95rem, 1.3vw, 1.1rem)', fontFamily: "'Geist', sans-serif", fontWeight: 400 }}>Connect a provider key and start tracking tokens, cost and latency in minutes.</p>
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-center gap-[12px]">
            <Link to="/dashboard" className="btn-chunky h-[44px] px-[24px] text-sm font-semibold text-[#171412] transition-colors flex items-center justify-center gap-2" style={{ background: BTN }}>
              Open Dashboard <ArrowRight className="w-4 h-4" />
            </Link>
            <Link to="/docs" className="btn-chunky h-[44px] px-[24px] text-sm font-semibold transition-colors flex items-center justify-center gap-2" style={{ color: INK }}>
              Read the Docs
            </Link>
          </div>
        </motion.div>
      </div>
    </section>
  );
}

/* ═══════════ FOOTER ═══════════ */
function Footer() {
  const footerLinks = {
    Product: ['AI Gateway', 'Observability', 'Guardrails', 'Governance'],
    Developers: ['Documentation', 'API Reference', 'Quickstart', 'GitHub', 'Changelog'],
    Resources: ['Blog', 'Community', 'Status', 'Support', 'Cookbooks'],
    Company: ['About', 'Careers', 'Contact', 'Privacy', 'Terms'],
  };

  return (
    <footer style={{ /* ponytail: no section borders — video BG */ }}>
      <div className={`${C} py-[48px]`}>
        <div className="grid sm:grid-cols-2 lg:grid-cols-6 gap-[32px]">
          <div className="lg:col-span-2">
            <div className="flex items-center gap-[8px] mb-[12px]">
              <img src="/footer-logo.png" alt="ReRouteAI" className="h-[48px] w-auto object-contain" />
              <span className="text-[15px] font-semibold" style={{ color: INK }}>ReRouteAI</span>
            </div>
            <p className="text-sm leading-relaxed max-w-[300px] mb-[20px]" style={{ color: MUTED }}>OpenAI-compatible gateway. Every request logged — tokens, cost, latency.</p>
            <div className="flex items-center gap-[16px]">
              {['GitHub', 'Discord', 'LinkedIn', 'X'].map((s) => (
                <a key={s} href="#" className="text-[13px] hover:underline" style={{ color: FAINT }}>{s}</a>
              ))}
            </div>
          </div>
          {Object.entries(footerLinks).map(([title, links]) => (
            <div key={title}>
              <p className="text-[13px] font-semibold mb-[12px]" style={{ color: INK }}>{title}</p>
              <ul className="space-y-[8px]">
                {links.map((l) => (
                  <li key={l}>
                    <a href="#" className="text-sm hover:underline" style={{ color: MUTED }}>{l}</a>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <div className="mt-[32px] pt-[24px] flex flex-col sm:flex-row items-center justify-between gap-[12px]" style={{ /* ponytail: no section borders — video BG */ }}>
          <p className="text-[13px]" style={{ color: FAINT }}>© 2026 ReRouteAI. All rights reserved.</p>
          <div className="flex items-center gap-[16px]">
            {['Privacy', 'Terms', 'Security'].map((l) => (
              <a key={l} href="#" className="text-[13px] hover:underline" style={{ color: FAINT }}>{l}</a>
            ))}
          </div>
        </div>
      </div>
    </footer>
  );
}

/* ═══════════ MAIN ═══════════ */
export default function Landing() {
  return (
    <div className="min-h-screen relative" style={{ background: '#000000' }}>
      {/* pitch-black stage: video + Backdrop removed for testing */}
      <div className="fixed inset-0 pointer-events-none z-[2]" style={{ background: 'radial-gradient(ellipse at center, transparent 55%, rgba(0,0,0,0.85) 100%)' }} />
      <div className="relative z-[1]">
        <HeroSection />
        <FeaturesSection />
        <WhySection />
        <ProductShowcase />
        <IntegrationsSection />
        <DeveloperExperience />
        <FAQSection />
        <FinalCTA />
        <Footer />
      </div>
    </div>
  );
}
