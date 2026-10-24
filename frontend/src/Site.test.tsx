// @vitest-environment jsdom
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom/vitest';
import Site from './Site';

vi.mock('./App', () => ({ default: () => <h1>Staff portal</h1> }));

beforeEach(() => { localStorage.clear(); vi.stubGlobal('fetch', vi.fn(() => new Promise(() => {}))); vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(null); });
afterEach(() => {
  cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals();
  document.documentElement.lang = 'en'; document.documentElement.dir = 'ltr';
});

test('public home opens without authentication requests and links to staff access', () => {
  render(<Site path="/" />);
  expect(screen.getByRole('heading', { level: 1, name: 'Good starts close to home' })).toBeInTheDocument();
  expect(vi.mocked(fetch).mock.calls.every(([path]) => path === '/api/public/catalog')).toBe(true);
  expect(screen.getAllByRole('link', { name: 'Staff sign-in' })[0]).toHaveAttribute('href', '/staff');
  for (const link of screen.getAllByRole('link')) {
    const href = link.getAttribute('href');
    if (href?.startsWith('#')) expect(document.getElementById(href.slice(1))).not.toBeNull();
  }
});

test('direct staff path preserves the staff portal', () => {
  render(<Site path="/staff" />);
  expect(screen.getByRole('heading', { name: 'Staff portal' })).toBeInTheDocument();
});

test('participation shows one panel and changes through accessible step controls', async () => {
  const user = userEvent.setup();
  render(<Site path="/" />);
  expect(screen.getAllByRole('article')).toHaveLength(1);
  expect(screen.queryByText(/Bring your practical experience/, { selector: 'p' })).not.toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: 'Share your skills' }));
  expect(screen.getByText(/Bring your practical experience/, { selector: 'p' })).toBeInTheDocument();
  expect(screen.queryByText(/Join local activities and work alongside/, { selector: 'p' })).not.toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: 'Support local work' }));
  expect(screen.getByText(/This website does not collect online payments/, { selector: 'p' })).toBeInTheDocument();
});

test('About has its own content, page navigation and localized metadata', async () => {
  const user = userEvent.setup();
  render(<Site path="/about" />);
  expect(screen.getByRole('heading', { level: 1, name: 'Local work. Shared direction.' })).toBeInTheDocument();
  expect(screen.getByRole('heading', { name: 'How we work together' })).toBeInTheDocument();
  expect(screen.getAllByRole('link', { name: 'About' })[0]).toHaveAttribute('aria-current', 'page');
  expect(screen.getAllByRole('link', { name: 'Programs' })[0]).toHaveAttribute('href', '/programs');
  expect(document.title).toBe('About | Branch Office');
  await user.click(screen.getByRole('button', { name: 'اردو' }));
  expect(document.documentElement.dir).toBe('rtl');
  expect(document.title).toBe('تعارف | برانچ آفس');
  expect(vi.mocked(fetch).mock.calls.every(([path]) => path === '/api/public/catalog')).toBe(true);
});

test.each([
  ['/programs', 'Make your time count'], ['/branches', 'A local connection'],
  ['/events', 'Make room for community'], ['/get-involved', 'Your time matters'], ['/contact', 'Keep in touch'],
])('%s opens directly as a separate public page', (path, heading) => {
  render(<Site path={path} />);
  expect(screen.getByRole('heading', { level: 1, name: heading })).toBeInTheDocument();
  expect(vi.mocked(fetch).mock.calls.every(([path]) => path === '/api/public/catalog')).toBe(true);
  expect(screen.queryByRole('img')).not.toBeInTheDocument();
});

test('a returning visitor starts in their saved language', () => {
  localStorage.setItem('branch-office-language', 'ur');
  render(<Site path="/" />);
  expect(document.documentElement).toHaveAttribute('dir', 'rtl');
  expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('بھلائی کا آغاز اپنے محلے سے');
});

test('unknown public paths offer a working home destination', () => {
  render(<Site path="/not-a-page" />);
  expect(screen.getByRole('heading', { name: 'Page not found' })).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Go home' })).toHaveAttribute('href', '/');
});

test('language switching translates content, uses RTL and remembers the choice', async () => {
  const user = userEvent.setup();
  render(<Site path="/" />);
  await user.click(screen.getByRole('button', { name: 'اردو' }));
  expect(document.documentElement).toHaveAttribute('lang', 'ur');
  expect(document.documentElement).toHaveAttribute('dir', 'rtl');
  expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('بھلائی کا آغاز اپنے محلے سے');
  expect(localStorage.getItem('branch-office-language')).toBe('ur');
  await user.click(screen.getByRole('button', { name: 'English' }));
  expect(document.documentElement).toHaveAttribute('dir', 'ltr');
});

test('mobile menu closes on Escape and returns focus to its trigger', async () => {
  const user = userEvent.setup();
  render(<Site path="/" />);
  const trigger = screen.getByRole('button', { name: 'Open menu' });
  await user.click(trigger);
  expect(trigger).toHaveAttribute('aria-expanded', 'true');
  await user.keyboard('{Escape}');
  expect(trigger).toHaveAttribute('aria-expanded', 'false');
  expect(trigger).toHaveFocus();
});

test('home and language switching still work when browser storage is denied', async () => {
  vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('Denied'); });
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('Denied'); });
  const user = userEvent.setup();
  render(<Site path="/" />);
  await user.click(screen.getByRole('button', { name: 'اردو' }));
  expect(document.documentElement).toHaveAttribute('dir', 'rtl');
  expect(vi.mocked(fetch).mock.calls.every(([path]) => path === '/api/public/catalog')).toBe(true);
});
