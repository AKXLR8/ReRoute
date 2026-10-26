import { useState } from 'react';
import { Check, Copy } from 'lucide-react';

/** Read-only value with a copy button. Never used for secrets that outlive creation. */
export function CopyField({ value, className = '' }: { value: string; className?: string }) {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      // clipboard blocked - the value stays selectable
    }
  };

  return (
    <div
      className={`flex items-center gap-2 h-9 pl-3 pr-1 rounded-lg border border-[var(--border)] bg-black ${className}`}
    >
      <code className="flex-1 min-w-0 truncate font-mono text-[12px] text-[var(--text-secondary)]">
        {value}
      </code>
      <button
        type="button"
        onClick={copy}
        aria-label="Copy to clipboard"
        className="h-7 px-2 rounded-md flex items-center gap-1.5 text-[11px] font-medium text-[var(--text-muted)] hover:text-white hover:bg-[var(--hover)] transition-colors"
      >
        {copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
        {copied ? 'Copied' : 'Copy'}
      </button>
    </div>
  );
}
