import { useState, useEffect, createContext, useContext, type ReactNode } from 'react';
import { X, AlertCircle } from 'lucide-react';

interface RateLimitToast {
  id: number;
  message: string;
  retryAfter: number;
  startTime: number;
}

interface ToastContextValue {
  toasts: RateLimitToast[];
  addToast: (msg: string, retryAfter: number) => void;
  removeToast: (id: number) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<RateLimitToast[]>([]);

  const addToast = (message: string, retryAfter: number) => {
    const id = Date.now();
    setToasts((prev) => [...prev, { id, message, retryAfter, startTime: Date.now() }]);
  };

  const removeToast = (id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  // Auto-remove expired toasts
  useEffect(() => {
    if (toasts.length === 0) return;
    const interval = setInterval(() => {
      const now = Date.now();
      setToasts((prev) => prev.filter((t) => {
        const elapsed = (now - t.startTime) / 1000;
        return elapsed < t.retryAfter + 2; // keep 2s after retry
      }));
    }, 1000);
    return () => clearInterval(interval);
  }, [toasts.length]);

  return (
    <ToastContext.Provider value={{ toasts, addToast, removeToast }}>
      {children}
      <div className="fixed bottom-4 right-4 z-[1000] flex flex-col gap-2 pointer-events-none">
        {toasts.map((t) => (
          <RateLimitToastItem key={t.id} toast={t} onClose={removeToast} />
        ))}
      </div>
    </ToastContext.Provider>
  );
}

function RateLimitToastItem({ toast, onClose }: { toast: RateLimitToast; onClose: (id: number) => void }) {
  const [progress, setProgress] = useState(100);

  useEffect(() => {
    const start = toast.startTime;
    const duration = toast.retryAfter * 1000;
    const interval = setInterval(() => {
      const elapsed = Date.now() - start;
      const pct = Math.max(0, 100 - (elapsed / duration) * 100);
      setProgress(pct);
      if (pct === 0) clearInterval(interval);
    }, 200);
    return () => clearInterval(interval);
  }, [toast.retryAfter, toast.startTime]);

  const remaining = Math.ceil(Math.max(0, toast.retryAfter - (Date.now() - toast.startTime) / 1000));

  return (
    <div className="pointer-events-auto w-[320px] rounded-lg border border-amber-500/50 bg-amber-900/90 backdrop-blur-sm shadow-lg p-3 animate-slide-in">
      <div className="flex items-start gap-2">
        <AlertCircle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-amber-100">Rate limit exceeded</p>
          <p className="text-xs text-amber-300 mt-0.5 truncate">{toast.message}</p>
          <div className="mt-2 h-1.5 rounded-full bg-amber-800 overflow-hidden">
            <div
              className="h-full bg-amber-400 transition-all duration-200 ease-linear"
              style={{ width: `${progress}%` }}
            />
          </div>
          <p className="text-[10px] text-amber-500 mt-1 font-mono tabular-nums">
            Retry in {remaining}s
          </p>
        </div>
        <button
          onClick={() => onClose(toast.id)}
          className="text-amber-400 hover:text-amber-200 transition-colors shrink-0"
          aria-label="Dismiss"
        >
          <X className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}

let toastInstance: ToastContextValue | null = null;

export function initToast(instance: ToastContextValue) {
  toastInstance = instance;
}

export function getToast() {
  return toastInstance;
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used within ToastProvider');
  return ctx;
}