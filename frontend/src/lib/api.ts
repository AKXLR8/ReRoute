
import { accessToken, clearSession, refreshSession } from './auth';

export const API_URL = 'https://re-route-pi.vercel.app';

interface ApiError {
  status: number;
  detail?: string;
  retryAfter?: number;
}

async function request<T>(path: string, opts?: RequestInit): Promise<T> {
  const send = () => {
    const token = accessToken();

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      Accept: 'application/json',
      ...((opts?.headers as Record<string, string>) ?? {}),
    };

    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    return fetch(`${API_URL}${path}`, {
      ...opts,
      headers,
    });
  };

  let res = await send();

  // Expired access token → attempt one silent refresh.
  if (res.status === 401 && accessToken()) {
    if (await refreshSession()) {
      res = await send();
    } else {
      clearSession();
      window.dispatchEvent(new Event('auth:expired'));
      throw new Error('401: Session expired');
    }
  }

  if (!res.ok) {
    let detail: string | undefined;
    let retryAfter: number | undefined;

    const retryHeader = res.headers.get('Retry-After');

    if (retryHeader) {
      retryAfter = Number(retryHeader);
    }

    try {
      const json = await res.json();
      detail = json.detail ?? JSON.stringify(json);
    } catch {
      detail = await res.text() || res.statusText;
    }

    // Show rate-limit toast.
    if (res.status === 429) {
      const toast = await import('./toast').then((m) => m.getToast());

      if (toast) {
        toast.addToast(detail || 'Too many requests', retryAfter || 60);
      }
    }

    const err = new Error(`${res.status}: ${detail}`) as Error & ApiError;
    err.status = res.status;
    err.detail = detail;
    err.retryAfter = retryAfter;

    throw err;
  }

  if (res.status === 204) {
    return undefined as T;
  }

  return res.json();
}

export interface AuditLog {
  id: string;
  timestamp: string;
  provider: string;
  model_requested: string;
  model_served: string;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
  latency_ms: number;
  status_code: number;
  error_message: string | null;
  ttft_ms: number | null;
  tokens_per_sec: number | null;
  finish_reason: string | null;
  is_cached: boolean;
  cache_saved_usd: number;
  trace_id: string | null;
  fallback_from: string | null;
  retry_count: number;
  is_stream: boolean;
}

/* BYOK — connected provider key (write-only; server returns masked). */
export interface ProviderKey {
  provider: string;
  base_url: string | null;
  key_masked: string;
  created_at: string | null;
}

export interface ModelInfo {
  id: string;
  owned_by: string;
  providers: string[];
}

export interface ModelsResponse {
  data: ModelInfo[];
  object: string;
}

export const providerDisplay: Record<string, string> = {
  openai: 'OpenAI',
  anthropic: 'Anthropic',
  cerebras: 'Cerebras',
  gemini: 'Google',
  groq: 'Groq',
  mercury: 'Mercury',
  ollama: 'Ollama',
  together: 'Together',
};

export const providerColor: Record<string, string> = {
  openai: '#22C55E',
  anthropic: '#A855F7',
  cerebras: '#FB923C',
  gemini: '#3B82F6',
  groq: '#EAB308',
  mercury: '#EC4899',
  ollama: '#06B6D4',
  together: '#84CC16',
};

export const displayName = (provider: string) =>
  providerDisplay[provider] ?? provider;

export const displayColor = (provider: string) =>
  providerColor[provider] ?? '#6B7280';

export interface Analytics {
  provider: string;
  total_requests: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_cost_usd: number;
  avg_latency_ms: number;
  avg_ttft_ms: number | null;
  avg_tokens_per_sec: number | null;
  truncated: number;
  cache_saved_usd: number;
}

export interface ActivityDay {
  date: string;
  requests: number;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
  avg_latency_ms: number;
  cached: number;
  avg_ttft_ms: number | null;
  avg_tokens_per_sec: number | null;
  cache_saved_usd: number;
}

export interface BreakdownProvider {
  name: string | null;
  requests: number;
  cost_usd: number;
}

export interface BreakdownModel {
  model: string | null;
  requests: number;
  cost_usd: number;
  avg_latency_ms: number;
  avg_ttft_ms: number | null;
  avg_tokens_per_sec: number | null;
  truncated: number;
}

export interface FinishReason {
  reason: string;
  count: number;
}

export interface Breakdown {
  by_provider: BreakdownProvider[];
  by_model: BreakdownModel[];
  by_finish_reason: FinishReason[];
}

export interface UserInfo {
  id: string;
  email: string;
  role: 'admin' | 'member';
  is_active: boolean;
  last_login_at: string | null;
  created_at: string;
}

export interface ApiKey {
  id: string;
  name: string;
  key_prefix: string;
  created_at: string;
  last_used_at: string | null;
  revoked_at: string | null;
}

export interface ApiKeyCreated extends ApiKey {
  key: string;
}

export const api = {
  // Gateway API keys (session-only: a key cannot manage keys)
  listApiKeys: () => request<ApiKey[]>('/auth/api-keys'),

  createApiKey: (name: string) =>
    request<ApiKeyCreated>('/auth/api-keys', {
      method: 'POST',
      body: JSON.stringify({ name }),
    }),

  revokeApiKey: (id: string) =>
    request<void>(`/auth/api-keys/${id}`, { method: 'DELETE' }),

  // Per-user BYOK
  listProviders: () => request<ProviderKey[]>('/auth/providers'),

  connectProvider: (provider: string, apiKey: string, baseUrl?: string) =>
    request<ProviderKey>(`/auth/providers/${provider}`, {
      method: 'PUT',
      body: JSON.stringify({
        api_key: apiKey,
        base_url: baseUrl || null,
      }),
    }),

  disconnectProvider: (provider: string) =>
    request<void>(`/auth/providers/${provider}`, {
      method: 'DELETE',
    }),

  // Logs
  listLogs: (limit = 100) =>
    request<AuditLog[]>(`/admin/logs?limit=${limit}`),

  // Analytics
  getAnalytics: (days = 7) =>
    request<Analytics[]>(`/admin/analytics?days=${days}`),

  // Per-day activity
  getActivity: (days = 7) =>
    request<ActivityDay[]>(`/admin/activity?days=${days}`),

  // Provider/model breakdown
  getBreakdown: (days = 7) =>
    request<Breakdown>(`/admin/breakdown?days=${days}`),

  // Live model registry
  listModels: () =>
    request<ModelsResponse>('/v1/models'),

  // Health
  getHealth: () =>
    request<{
      circuit_breakers: Record<
        string,
        {
          state: string;
          failure_count: number;
          is_available: boolean;
        }
      >;
    }>('/admin/health'),

  // Account management
  listUsers: () =>
    request<UserInfo[]>('/admin/users'),

  createUser: (
    email: string,
    password: string,
    role: 'admin' | 'member',
  ) =>
    request<UserInfo>('/admin/users', {
      method: 'POST',
      body: JSON.stringify({ email, password, role }),
    }),

  updateUser: (
    id: string,
    patch: { role?: string; is_active?: boolean },
  ) =>
    request<UserInfo>(`/admin/users/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(patch),
    }),

  resetUserPassword: (id: string, newPassword: string) =>
    request<void>(`/admin/users/${id}/password`, {
      method: 'POST',
      body: JSON.stringify({ new_password: newPassword }),
    }),

  deleteUser: (id: string) =>
    request<void>(`/admin/users/${id}`, {
      method: 'DELETE',
    }),
};
