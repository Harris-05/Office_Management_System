// @vitest-environment jsdom
import { afterEach, expect, test, vi } from 'vitest';
import { watchScroll } from './scrollMotion';

afterEach(() => vi.unstubAllGlobals());
test('scroll updates still work without animation frames and stop after cleanup', () => {
  vi.stubGlobal('requestAnimationFrame', undefined);
  const update = vi.fn();
  const watcher = watchScroll(update);
  expect(update).toHaveBeenCalledTimes(1);
  window.dispatchEvent(new Event('scroll'));
  expect(update).toHaveBeenCalledTimes(2);
  watcher.stop();
  window.dispatchEvent(new Event('scroll'));
  expect(update).toHaveBeenCalledTimes(2);
});
