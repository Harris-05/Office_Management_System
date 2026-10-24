// @vitest-environment jsdom
import { useRef } from 'react';
import { act, cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import useScrollMotion from './useScrollMotion';

let callbacks: IntersectionObserverCallback[];
const observe = vi.fn();
const unobserve = vi.fn();
const disconnect = vi.fn();

function Example({ revision = 'en' }: { revision?: string }) {
  const root = useRef<HTMLDivElement>(null);
  useScrollMotion(root, revision);
  return <div ref={root} data-testid="motion-root"><section className="home-hero"><p key={revision} data-home-reveal>{revision === 'en' ? 'Community information' : 'مقامی معلومات'}</p></section></div>;
}

beforeEach(() => {
  callbacks = [];
  vi.clearAllMocks();
  vi.stubGlobal('IntersectionObserver', class {
    constructor(callback: IntersectionObserverCallback) { callbacks.push(callback); }
    observe = observe;
    unobserve = unobserve;
    disconnect = disconnect;
  });
  vi.stubGlobal('requestAnimationFrame', vi.fn(() => 1));
  vi.stubGlobal('cancelAnimationFrame', vi.fn());
  vi.stubGlobal('matchMedia', vi.fn(() => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() })));
  vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockReturnValue({ top: 1200, bottom: 1240, height: 40, width: 300, left: 0, right: 300, x: 0, y: 1200, toJSON: () => ({}) });
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

test('offscreen content reveals once it actually enters the viewport', () => {
  render(<Example />);
  const text = screen.getByText('Community information');
  expect(text).toHaveClass('home-reveal-pending');
  const bounds = text.getBoundingClientRect();
  const entry: IntersectionObserverEntry = { target: text, isIntersecting: true, intersectionRatio: 1, boundingClientRect: bounds, intersectionRect: bounds, rootBounds: null, time: 0 };
  const observer: IntersectionObserver = { observe, unobserve, disconnect, takeRecords: () => [], root: null, rootMargin: '0px', thresholds: [.12] };
  act(() => callbacks[0]([entry], observer));
  expect(text).not.toHaveClass('home-reveal-pending');
  expect(text).toHaveClass('home-seen');
  expect(unobserve).toHaveBeenCalledWith(text);
});

test('content remains visible when IntersectionObserver is unavailable', () => {
  vi.stubGlobal('IntersectionObserver', undefined);
  render(<Example />);
  expect(screen.getByText('Community information')).not.toHaveClass('home-reveal-pending');
});

test('reduced motion never prepares content in a hidden state', () => {
  vi.stubGlobal('matchMedia', vi.fn(() => ({ matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() })));
  render(<Example />);
  expect(screen.getByText('Community information')).not.toHaveClass('home-reveal-pending');
  expect(observe).not.toHaveBeenCalled();
});

test('replacement language content is observed and cleanup releases pending elements', () => {
  const { rerender, unmount } = render(<Example />);
  const oldText = screen.getByText('Community information');
  rerender(<Example revision="ur" />);
  const newText = screen.getByText('مقامی معلومات');
  expect(oldText).not.toHaveClass('home-reveal-pending');
  expect(observe).toHaveBeenCalledWith(newText);
  expect(newText).toHaveClass('home-reveal-pending');
  unmount();
  expect(newText).not.toHaveClass('home-reveal-pending');
  expect(disconnect).toHaveBeenCalled();
});

test('scroll progress reflects the document position', () => {
  vi.spyOn(document.documentElement, 'scrollHeight', 'get').mockReturnValue(2400);
  vi.stubGlobal('innerHeight', 800);
  vi.stubGlobal('scrollY', 800);
  render(<Example />);
  act(() => vi.mocked(requestAnimationFrame).mock.calls[0][0](0));
  const root = screen.getByTestId('motion-root');
  expect(root.style.getPropertyValue('--home-page-progress')).toBe('0.5');
});

test('scroll updates share one frame and unmount removes listeners and queued work', () => {
  const { unmount } = render(<Example />);
  const root = screen.getByTestId('motion-root');
  act(() => vi.mocked(requestAnimationFrame).mock.calls[0][0](0));
  act(() => {
    window.dispatchEvent(new Event('scroll'));
    window.dispatchEvent(new Event('scroll'));
    window.dispatchEvent(new Event('resize'));
  });
  expect(requestAnimationFrame).toHaveBeenCalledTimes(2);
  unmount();
  expect(cancelAnimationFrame).toHaveBeenCalledWith(1);
  expect(root.style.getPropertyValue('--home-page-progress')).toBe('');
  window.dispatchEvent(new Event('scroll'));
  expect(requestAnimationFrame).toHaveBeenCalledTimes(2);
});
