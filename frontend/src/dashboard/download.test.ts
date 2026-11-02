// @vitest-environment jsdom
import {afterEach, expect, test, vi} from 'vitest';
import {downloadCollections} from './download';

afterEach(() => {vi.restoreAllMocks(); vi.unstubAllGlobals(); vi.useRealTimers();});

test('downloads the complete authenticated CSV response with a filename', async () => {
  vi.useFakeTimers();
  const fetcher = vi.fn().mockResolvedValue(new Response('\ufeff"Collection code"\r\n"COL-000001"', {headers: {'Content-Type': 'text/csv'}}));
  vi.stubGlobal('fetch', fetcher);
  const create = vi.fn().mockReturnValue('blob:synthetic-csv');
  const revoke = vi.fn();
  Object.defineProperty(URL, 'createObjectURL', {configurable: true, value: create});
  Object.defineProperty(URL, 'revokeObjectURL', {configurable: true, value: revoke});
  let clicked: HTMLAnchorElement | null = null;
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function () {clicked = this;});
  await downloadCollections('branch_id=branch&date_from=2020-01-01');
  expect(fetcher).toHaveBeenCalledWith('/api/dashboard/export.csv?branch_id=branch&date_from=2020-01-01', expect.objectContaining({credentials: 'same-origin'}));
  expect(clicked!.download).toBe('collections.csv');
  expect(clicked!.href).toBe('blob:synthetic-csv');
  expect(create.mock.calls[0][0]).toBeInstanceOf(Blob);
  expect(document.querySelector('a')).toBeNull();
  vi.advanceTimersByTime(1000);
  expect(revoke).toHaveBeenCalledWith('blob:synthetic-csv');
});

test('expired export sessions notify the staff shell and never save an error document', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({detail: 'Sign in again.'}), {status: 401})));
  const invalid = vi.fn();
  window.addEventListener('branch-session-invalid', invalid);
  try {
    await expect(downloadCollections('')).rejects.toThrow('Sign in again.');
    expect(invalid).toHaveBeenCalledOnce();
    expect(document.querySelector('a')).toBeNull();
  } finally {window.removeEventListener('branch-session-invalid', invalid);}
});

test('network download failures remain actionable errors', async () => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')));
  await expect(downloadCollections('')).rejects.toThrow('Check your connection');
});
