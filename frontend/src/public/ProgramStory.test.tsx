// @vitest-environment jsdom
import { act, cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import ProgramStory from './ProgramStory';

let top = 100;
let frames: FrameRequestCallback[];
beforeEach(() => {
  top = 100; frames = [];
  history.replaceState(null, '', '/');
  vi.stubGlobal('innerHeight', 900);
  vi.stubGlobal('matchMedia', vi.fn(() => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() })));
  vi.stubGlobal('requestAnimationFrame', vi.fn(callback => { frames.push(callback); return frames.length; }));
  vi.stubGlobal('cancelAnimationFrame', vi.fn());
  vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(function (this: HTMLElement) {
    return new DOMRect(0, this.id === 'programs' ? top : 0, 1200, this.id === 'programs' ? 2400 : 700);
  });
  vi.spyOn(window, 'scrollTo').mockImplementation(() => {});
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); history.replaceState(null, '', '/'); });

test('fractional viewport rounding does not repeatedly collapse and re-pin the story while scrolling', () => {
  vi.stubGlobal('innerHeight', 667);
  vi.mocked(HTMLElement.prototype.getBoundingClientRect).mockImplementation(function (this: HTMLElement) {
    if (this.id === 'programs') return new DOMRect(0, top, 375, 1600);
    const isPinned = document.getElementById('programs')?.dataset.pinned === 'true';
    return new DOMRect(0, 0, 375, isPinned ? 667.3333 : 650);
  });
  const { container } = render(<ProgramStory language="en" />);
  for (let index = 0; index < 6; index++) {
    act(() => { top -= 60; window.dispatchEvent(new Event('scroll')); frames.splice(0).forEach(frame => frame(0)); });
    expect(container.querySelector('#programs')).toHaveAttribute('data-pinned', 'true');
  }
});

test('only one panel is exposed; manual selection and keyboard controls change its paragraph', async () => {
  const user = userEvent.setup();
  render(<ProgramStory language="en" />);
  expect(screen.getAllByRole('article')).toHaveLength(1);
  expect(screen.getByRole('button', { name: 'Previous step' })).toBeDisabled();
  await user.click(screen.getByRole('button', { name: 'Share your skills' }));
  expect(screen.getByText(/Bring your practical experience/, { selector: 'p' })).toBeVisible();
  expect(screen.queryByText(/Join local activities and work alongside/, { selector: 'p' })).not.toBeInTheDocument();
  const next = screen.getByRole('button', { name: 'Next step' });
  next.focus(); await user.keyboard('{Enter}');
  expect(screen.getByText(/This website does not collect online payments/, { selector: 'p' })).toBeVisible();
  expect(next).toBeDisabled();
});

test('native forward and reverse scroll choose one paragraph and cleanup releases listeners', () => {
  const { unmount } = render(<ProgramStory language="en" />);
  const tick = (nextTop: number) => act(() => { top = nextTop; window.dispatchEvent(new Event('scroll')); frames.splice(0).forEach(frame => frame(0)); });
  tick(-800);
  expect(screen.getByRole('button', { name: 'Share your skills' })).toHaveAttribute('aria-pressed', 'true');
  tick(-1500);
  expect(screen.getByText(/This website does not collect online payments/, { selector: 'p' })).toBeInTheDocument();
  tick(-800);
  expect(screen.getByText(/Bring your practical experience/, { selector: 'p' })).toBeInTheDocument();
  tick(100);
  expect(screen.getByText(/Join local activities and work alongside/, { selector: 'p' })).toBeInTheDocument();
  unmount();
  const calls = vi.mocked(requestAnimationFrame).mock.calls.length;
  window.dispatchEvent(new Event('scroll'));
  expect(requestAnimationFrame).toHaveBeenCalledTimes(calls);
});

test('reduced motion keeps a single manual panel without forcing scroll', async () => {
  vi.stubGlobal('matchMedia', vi.fn(() => ({ matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() })));
  const user = userEvent.setup();
  render(<ProgramStory language="ur" />);
  await user.click(screen.getByRole('button', { name: 'اپنا ہنر بانٹیں' }));
  expect(screen.getAllByRole('article')).toHaveLength(1);
  expect(screen.getByText(/اپنا تجربہ/, { selector: 'p' })).toBeVisible();
  expect(window.scrollTo).not.toHaveBeenCalled();
});

test('a direct participation hash selects its paragraph and survives language replacement', () => {
  history.replaceState(null, '', '/#participation-2');
  vi.stubGlobal('matchMedia', vi.fn(() => ({ matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() })));
  const { rerender } = render(<ProgramStory language="en" />);
  expect(screen.getByText(/Bring your practical experience/, { selector: 'p' })).toBeInTheDocument();
  screen.getByRole('button', { name: 'Share your skills' }).focus();
  rerender(<ProgramStory language="ur" />);
  expect(screen.getByText(/اپنا تجربہ/, { selector: 'p' })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'اپنا ہنر بانٹیں' })).toHaveFocus();
});
