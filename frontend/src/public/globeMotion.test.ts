// @vitest-environment jsdom
import { afterEach, expect, test, vi } from 'vitest';
import { animateGlobe } from './globeMotion';

afterEach(() => vi.unstubAllGlobals());
test('globe spins without scrolling and scroll adds motion without a jump', () => {
  let callback: FrameRequestCallback = () => {};
  vi.stubGlobal('requestAnimationFrame', vi.fn(next => { callback = next; return 1; }));
  vi.stubGlobal('cancelAnimationFrame', vi.fn());
  let progress = 0;
  const paint = vi.fn();
  const animation = animateGlobe({ readProgress: () => progress, isMoving: () => true, paint });
  callback(0); callback(50); callback(100);
  const idle = paint.mock.calls.at(-1)![0];
  expect(idle).toBeGreaterThan(-.4);
  progress = 1; animation.refresh(); callback(150);
  const afterScroll = paint.mock.calls.at(-1)![0];
  expect(afterScroll).toBeGreaterThan(idle);
  expect(afterScroll - idle).toBeLessThan(1.6);
  animation.stop();
  expect(cancelAnimationFrame).toHaveBeenCalled();
});

test('pause/reduced/hidden modes stop scheduling and resume without a time jump', () => {
  let callback: FrameRequestCallback = () => {};
  vi.stubGlobal('requestAnimationFrame', vi.fn(next => { callback = next; return 1; }));
  vi.stubGlobal('cancelAnimationFrame', vi.fn());
  let moving = true;
  const paint = vi.fn();
  const animation = animateGlobe({ readProgress: () => 0, isMoving: () => moving, paint });
  callback(0); callback(50);
  moving = false; animation.refresh();
  const frozen = paint.mock.calls.at(-1)![0];
  const count = vi.mocked(requestAnimationFrame).mock.calls.length;
  callback(1000);
  expect(requestAnimationFrame).toHaveBeenCalledTimes(count);
  expect(paint.mock.calls.at(-1)![0]).toBe(frozen);
  moving = true; animation.refresh(); callback(50000);
  expect(paint.mock.calls.at(-1)![0]).toBe(frozen);
  animation.stop();
});
