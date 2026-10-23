import type { User } from './types';

let csrfToken = '';
let boot: Promise<void> | null = null;

export class ApiError extends Error {
  constructor(public status: number, message: string, public retryAfter?: number) { super(message); }
}

async function request<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, {
      method, credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', ...(csrfToken ? { 'X-CSRF-Token': csrfToken } : {}) },
      ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
      signal: AbortSignal.timeout(15000),
    });
  } catch {
    throw new Error('Unable to connect. Check your connection and try again.');
  }
  const data = response.status === 204 ? undefined : await response.json().catch(() => undefined);
  if (!response.ok) {
    const retry = Number(response.headers.get('Retry-After')) || undefined;
    throw new ApiError(response.status, response.status === 429
      ? `Too many attempts. Please try again in ${retry ?? 60} seconds.`
      : typeof data?.detail === 'string' ? data.detail : 'Service unavailable. Please try again.', retry);
  }
  if (data?.csrf_token) csrfToken = data.csrf_token;
  return data as T;
}

export async function bootstrap(): Promise<void> {
  if (!boot) boot = request<{ csrf_token: string }>('/api/csrf').then(() => {}).finally(() => { boot = null; });
  return boot;
}

export async function api<T = unknown>(path: string, method = 'GET', body?: unknown): Promise<T> {
  if (method !== 'GET' && !csrfToken) await bootstrap();
  try {
    const result = await request<T>(path, method, body);
    if (path === '/api/logout') csrfToken = '';
    return result;
  } catch (error) {
    if (error instanceof ApiError && error.status === 401 && path !== '/api/login' && error.message !== 'Current password is incorrect.') {
      csrfToken = '';
      window.dispatchEvent(new Event('branch-session-invalid'));
    }
    if (error instanceof ApiError && error.status === 403 && error.message.startsWith('Request verification')) {
      await bootstrap();
      throw new ApiError(403, 'Page verification expired. Please try the action again.');
    }
    throw error;
  }
}

export async function restore(): Promise<User | null> {
  await bootstrap();
  try { return await request<User>('/api/me'); }
  catch (error) {
    if (error instanceof ApiError && error.status === 401) return null;
    throw error;
  }
}
