export interface Envelope<T> {
  ok: boolean;
  data: T;
  meta?: { page: number; limit: number; total: number };
  error?: { code: string; message: string };
}

interface RequestOptions {
  retryWithoutAuthOn401?: boolean;
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly code: string,
    readonly status: number
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

const API_URL = (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '');
const TOKEN_KEY = 'dnfg_token';

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function saveToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

export async function request<T>(
  endpoint: string,
  init: RequestInit = {},
  authenticated = true,
  options: RequestOptions = {}
): Promise<{ data: T; meta?: Envelope<T>['meta'] }> {
  const path = endpoint.replace(/^(GET|POST|PUT|PATCH|DELETE) /, '');
  const headers = new Headers(init.headers);
  const token = getToken();
  if (authenticated && token) headers.set('Authorization', `Bearer ${token}`);
  if (init.body && !(init.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  const response = await fetch(`${API_URL}${path}`, { ...init, headers });
  let envelope: Envelope<T>;
  try {
    envelope = (await response.json()) as Envelope<T>;
  } catch {
    throw new ApiError('Không thể đọc phản hồi từ máy chủ.', 'INVALID_RESPONSE', response.status);
  }
  if (!response.ok || !envelope.ok) {
    const code = envelope.error?.code ?? 'REQUEST_FAILED';
    const message = envelope.error?.message ?? 'Đã có lỗi xảy ra. Vui lòng thử lại.';
    if (response.status === 401 || code === 'UNAUTHORIZED') {
      clearToken();
      window.dispatchEvent(new Event('dnfg:logout'));
      if (options.retryWithoutAuthOn401 && authenticated && token) {
        return request(endpoint, init, false, { retryWithoutAuthOn401: false });
      }
      window.location.assign('/login');
    }
    if (code === 'BANNED') {
      window.dispatchEvent(new CustomEvent<string>('dnfg:banned', { detail: message }));
    }
    throw new ApiError(message, code, response.status);
  }
  return { data: envelope.data, meta: envelope.meta };
}

export function queryString(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && String(value).trim() !== '') search.set(key, String(value));
  });
  const value = search.toString();
  return value ? `?${value}` : '';
}
