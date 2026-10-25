
/* Account sessions — access JWT (15 min) + rotating refresh token, both in
   localStorage. api.ts attaches the Bearer header and auto-refreshes on 401;
   this module owns everything about "who is signed in".

   ponytail: localStorage (not httpOnly cookies) matches the existing X-API-Key
   storage model — XSS is equally fatal for both; cookies would add CSRF surface. */

const API_URL = 'https://re-route-pi.vercel.app';

const ACCESS = 'access_token';
const REFRESH = 'refresh_token';
const USER = 'session_user';

export interface SessionUser {
  id: string | null;
  email: string | null;
  role: 'admin' | 'member';
}

interface TokenResponse {
  access_token: string;
  refresh_token: string;
  expires_in: number;
  user: SessionUser;
}

export const accessToken = () => localStorage.getItem(ACCESS);

export const storedUser = (): SessionUser | null => {
  try {
    const raw = localStorage.getItem(USER);
    return raw ? (JSON.parse(raw) as SessionUser) : null;
  } catch {
    return null;
  }
};

export function saveSession(t: TokenResponse) {
  localStorage.setItem(ACCESS, t.access_token);
  localStorage.setItem(REFRESH, t.refresh_token);
  localStorage.setItem(USER, JSON.stringify(t.user));
}

export function clearSession() {
  localStorage.removeItem(ACCESS);
  localStorage.removeItem(REFRESH);
  localStorage.removeItem(USER);
  localStorage.removeItem('admin_api_key');
}

async function post<T>(
  path: string,
  body: unknown,
  headers: Record<string, string> = {},
): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...headers,
    },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const text = await res.text();

    if (res.status === 401) {
      throw new Error('Invalid email or password');
    }

    let detail = text;

    try {
      const json = JSON.parse(text);
      detail = json.detail ?? text;
    } catch {
      // Response was not JSON; retain the original text.
    }

    throw new Error(detail || `Request failed: ${res.status}`);
  }

  if (res.status === 204) {
    return undefined as T;
  }

  return res.json() as Promise<T>;
}

export function needsSetup(): Promise<{ needs_setup: boolean }> {
  return fetch(`${API_URL}/auth/setup`)
    .then((res) => {
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }

      return res.json() as Promise<{ needs_setup: boolean }>;
    })
    .catch(() => ({ needs_setup: false }));
}

export async function login(
  email: string,
  password: string,
): Promise<SessionUser> {
  const t = await post<TokenResponse>('/auth/login', {
    email,
    password,
  });

  saveSession(t);
  return t.user;
}

export async function register(
  email: string,
  password: string,
): Promise<SessionUser> {
  const t = await post<TokenResponse>('/auth/register', {
    email,
    password,
  });

  saveSession(t);
  return t.user;
}

export async function exchangeGithub(code: string): Promise<SessionUser> {
  const t = await post<TokenResponse>('/auth/github/exchange', {
    code,
  });

  saveSession(t);
  return t.user;
}

export async function setup(
  email: string,
  password: string,
  setupKey: string,
): Promise<SessionUser> {
  const t = await post<TokenResponse>(
    '/auth/setup',
    { email, password },
    { 'X-API-Key': setupKey },
  );

  saveSession(t);
  return t.user;
}

export async function changePassword(
  current_password: string,
  new_password: string,
): Promise<SessionUser> {
  const t = await post<TokenResponse>(
    '/auth/change-password',
    { current_password, new_password },
    authHeader(),
  );

  saveSession(t);
  return t.user;
}

export function authHeader(): Record<string, string> {
  const token = accessToken();

  return token ? { Authorization: `Bearer ${token}` } : {};
}

/** Validate the stored session once at boot: me → refresh → me, else signed out. */
export async function bootSession(): Promise<SessionUser | null> {
  const tryMe = async (): Promise<SessionUser | null> => {
    const token = accessToken();

    if (!token) {
      return null;
    }

    try {
      const res = await fetch(`${API_URL}/auth/me`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!res.ok) {
        return null;
      }

      const user = (await res.json()) as SessionUser;
      localStorage.setItem(USER, JSON.stringify(user));

      return user;
    } catch {
      return null;
    }
  };

  const user = await tryMe();

  if (user) {
    return user;
  }

  if (await refreshSession()) {
    return tryMe();
  }

  clearSession();
  return null;
}

let refreshing: Promise<boolean> | null = null;

/** Rotate the refresh token (single flight). false = session is dead. */
export function refreshSession(): Promise<boolean> {
  if (refreshing) {
    return refreshing;
  }

  const raw = localStorage.getItem(REFRESH);

  if (!raw) {
    return Promise.resolve(false);
  }

  refreshing = (async () => {
    try {
      const res = await fetch(`${API_URL}/auth/refresh`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          refresh_token: raw,
        }),
      });

      if (!res.ok) {
        return false;
      }

      saveSession((await res.json()) as TokenResponse);
      return true;
    } catch {
      return false;
    } finally {
      refreshing = null;
    }
  })();

  return refreshing;
}

export async function logout() {
  const raw = localStorage.getItem(REFRESH);

  clearSession();

  if (raw) {
    try {
      await post<void>('/auth/logout', {
        refresh_token: raw,
      });
    } catch {
      // Local session is already cleared.
    }
  }
}

