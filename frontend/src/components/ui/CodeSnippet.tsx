import { useState } from 'react';
import { API_URL } from '../../lib/api';

const LANGS = ['curl', 'python', 'node'] as const;
type Lang = (typeof LANGS)[number];

function snippetFor(lang: Lang, apiKey: string, model = 'mercury-2'): string {
  const base = `${API_URL}/v1`;
  if (lang === 'curl') {
    return [
      `curl ${base}/chat/completions \\`,
      `  -H "Authorization: Bearer ${apiKey}" \\`,
      '  -H "Content-Type: application/json" \\',
      `  -d '{"model":"${model}","messages":[{"role":"user","content":"hello"}]}'`,
    ].join('\n');
  }
  if (lang === 'python') {
    return [
      'from openai import OpenAI',
      '',
      `client = OpenAI(base_url="${base}", api_key="${apiKey}")`,
      'r = client.chat.completions.create(',
      `    model="${model}",`,
      '    messages=[{"role": "user", "content": "hello"}],',
      ')',
      'print(r.choices[0].message.content)',
    ].join('\n');
  }
  return [
    `const res = await fetch("${base}/chat/completions", {`,
    '  method: "POST",',
    `  headers: { Authorization: "Bearer ${apiKey}", "Content-Type": "application/json" },`,
    `  body: JSON.stringify({ model: "${model}", messages: [{ role: "user", content: "hello" }] }),`,
    '});',
    'console.log((await res.json()).choices[0].message.content);',
  ].join('\n');
}

export function CodeSnippet({ apiKey, model }: { apiKey: string; model?: string }) {
  const [lang, setLang] = useState<Lang>('curl');
  const [copied, setCopied] = useState(false);
  const code = snippetFor(lang, apiKey, model);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      // clipboard blocked - the code stays selectable
    }
  };

  return (
    <div className="rounded-xl overflow-hidden" style={{ background: '#000', border: '1px solid var(--border)' }}>
      <div className="flex items-center gap-1 px-2 py-1.5 border-b border-[var(--border)]">
        {LANGS.map((l) => (
          <button
            key={l}
            onClick={() => setLang(l)}
            className={`h-6 px-2 rounded-md text-[11px] font-medium transition-colors ${
              lang === l ? 'bg-white/10 text-white' : 'text-[var(--text-muted)] hover:text-white'
            }`}
          >
            {l}
          </button>
        ))}
        <button
          onClick={copy}
          aria-label="Copy code"
          className="ml-auto h-6 px-2 rounded-md text-[11px] font-medium text-[var(--text-muted)] hover:text-white hover:bg-[var(--hover)] transition-colors"
        >
          {copied ? 'Copied' : 'Copy'}
        </button>
      </div>
      <pre className="p-3 overflow-x-auto text-[11.5px] leading-relaxed font-mono text-[var(--text-secondary)]">
        {code}
      </pre>
    </div>
  );
}
