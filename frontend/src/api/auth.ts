import { API_URL, parseResponse, BackendError } from './client';

export interface AuthUser {
  id: string;
  email: string;
  full_name: string;
  role: string;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

const ACCESS_KEY = 'dxa_access_token';
const REFRESH_KEY = 'dxa_refresh_token';

export function getAccessToken(): string | null {
  return localStorage.getItem(ACCESS_KEY);
}

export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_KEY);
}

export function setTokens(tokens: TokenResponse): void {
  localStorage.setItem(ACCESS_KEY, tokens.access_token);
  localStorage.setItem(REFRESH_KEY, tokens.refresh_token);
}

export function clearTokens(): void {
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

export async function login(email: string, password: string): Promise<TokenResponse> {
  const response = await fetch(`${API_URL}/api/v1/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  const tokens = await parseResponse<TokenResponse>(response);
  setTokens(tokens);
  return tokens;
}

export async function register(
  email: string,
  fullName: string,
  password: string,
): Promise<AuthUser> {
  const response = await fetch(`${API_URL}/api/v1/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, full_name: fullName, password }),
  });
  return parseResponse<AuthUser>(response);
}

export async function refreshTokens(): Promise<TokenResponse> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) {
    throw new BackendError('AUTHENTICATION_REQUIRED', 'Сессия не найдена', null, 401);
  }

  const response = await fetch(`${API_URL}/api/v1/auth/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  const tokens = await parseResponse<TokenResponse>(response);
  setTokens(tokens);
  return tokens;
}

export async function getMe(): Promise<AuthUser> {
  const response = await authorizedFetch('/api/v1/auth/me');
  return parseResponse<AuthUser>(response);
}

export async function logout(): Promise<void> {
  const token = getAccessToken();
  try {
    if (token) {
      await fetch(`${API_URL}/api/v1/auth/logout`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
    }
  } finally {
    clearTokens();
  }
}

let refreshPromise: Promise<string> | null = null;

async function getFreshAccessToken(): Promise<string> {
  if (!refreshPromise) {
    refreshPromise = refreshTokens()
      .then((tokens) => tokens.access_token)
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

export async function authorizedFetch(
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  const token = getAccessToken();
  const headers = new Headers(init.headers);
  if (token) headers.set('Authorization', `Bearer ${token}`);

  let response = await fetch(path.startsWith('http') ? path : `${API_URL}${path}`, {
    ...init,
    headers,
  });

  if (response.status !== 401 || !getRefreshToken()) {
    return response;
  }

  try {
    const freshToken = await getFreshAccessToken();
    const retryHeaders = new Headers(init.headers);
    retryHeaders.set('Authorization', `Bearer ${freshToken}`);
    response = await fetch(path.startsWith('http') ? path : `${API_URL}${path}`, {
      ...init,
      headers: retryHeaders,
    });
    return response;
  } catch {
    clearTokens();
    return response;
  }
}

export async function fetchPreviewBlob(previewUrl: string): Promise<string> {
  const response = await authorizedFetch(previewUrl);
  if (!response.ok) {
    await parseResponse(response);
  }
  const blob = await response.blob();
  return URL.createObjectURL(blob);
}
