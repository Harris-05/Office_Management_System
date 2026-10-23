// @vitest-environment jsdom
import { afterEach, expect, test, vi } from 'vitest';
import { api, ApiError, bootstrap, restore } from './api';

afterEach(() => { vi.unstubAllGlobals(); });

function response(status: number, data: unknown, headers = {}) {
  return new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json', ...headers } });
}

test('expired protected request emits session invalidation', async () => {
  const expired = vi.fn();
  window.addEventListener('branch-session-invalid', expired);
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response(401, { detail: 'Authentication required.' })));
  await expect(api('/api/staff')).rejects.toBeInstanceOf(ApiError);
  expect(expired).toHaveBeenCalledTimes(1);
  window.removeEventListener('branch-session-invalid', expired);
});

test('wrong current password keeps authenticated state', async () => {
  const expired = vi.fn();
  window.addEventListener('branch-session-invalid', expired);
  vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(response(200, { csrf_token: 'csrf-test' })).mockResolvedValueOnce(response(401, { detail: 'Current password is incorrect.' })));
  await expect(api('/api/change-password', 'POST', {})).rejects.toThrow('Current password is incorrect.');
  expect(expired).not.toHaveBeenCalled();
  window.removeEventListener('branch-session-invalid', expired);
});

test('429 surfaces retry information without replaying a write', async () => {
  const fetcher = vi.fn().mockResolvedValue(response(429, { detail: 'Limited' }, { 'Retry-After': '25' }));
  vi.stubGlobal('fetch', fetcher);
  await expect(api('/api/staff')).rejects.toThrow('25 seconds');
  expect(fetcher).toHaveBeenCalledTimes(1);
});

test('restore treats anonymous 401 differently from service outage', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(response(200, { csrf_token: 'csrf-test' })).mockResolvedValueOnce(response(401, { detail: 'Authentication required.' })));
  expect(await restore()).toBeNull();
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response(503, { detail: 'Service unavailable.' })));
  await expect(restore()).rejects.toThrow('Service unavailable.');
});
