// @vitest-environment jsdom
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import { act, cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom/vitest';
import App from './App';
import { api, restore } from './api';

vi.mock('./api', async (importOriginal) => ({ ...await importOriginal<typeof import('./api')>(), api: vi.fn(), restore: vi.fn() }));
const admin = { id: 'one', name: 'Staff Admin', email: 'admin@example.test', role: 'Super Admin', must_change_password: false };
beforeEach(() => { history.replaceState(null, '', '/staff'); vi.clearAllMocks(); vi.mocked(api).mockResolvedValue([]); });
afterEach(cleanup);

test('finance opens collections directly and browser navigation returns to workspace', async () => {
  history.replaceState(null,'','/staff/collections');
  vi.mocked(restore).mockResolvedValue({...admin,role:'Finance Reviewer'});
  vi.mocked(api).mockResolvedValue({items:[],total:0,offset:0,limit:25,total_amount:'0.00',currency:'PKR',server_time:'2026-10-24T10:00:00Z'});
  render(<App initialPage="collections"/>);
  expect(await screen.findByRole('heading',{name:'Offline collections'})).toBeVisible();
  act(()=>{history.replaceState(null,'','/staff');window.dispatchEvent(new PopStateEvent('popstate'));});
  expect(await screen.findByRole('heading',{name:'Your workspace'})).toBeVisible();
});

test.each([['applications','Volunteer applications'],['members','Member register']] as const)('HR can open the direct %s route and return through browser navigation', async (page, heading) => {
  history.replaceState(null,'',`/staff/${page}`);
  vi.mocked(restore).mockResolvedValue({...admin,role:'HR Lead'});
  vi.mocked(api).mockResolvedValue({items:[],total:0,offset:0,limit:25});
  render(<App initialPage={page}/>);
  expect(await screen.findByRole('heading',{name:heading})).toBeVisible();
  expect(screen.queryByRole('button',{name:'Staff accounts'})).not.toBeInTheDocument();
  act(() => {history.replaceState(null,'','/staff');window.dispatchEvent(new PopStateEvent('popstate'));});
  expect(await screen.findByRole('heading',{name:'Your workspace'})).toBeVisible();
});

test('branch management has a direct URL and browser navigation returns to workspace', async () => {
  vi.mocked(restore).mockResolvedValue(admin);
  vi.mocked(api).mockResolvedValue({items:[],total:0,offset:0,limit:25});
  render(<App />);
  await userEvent.click(await screen.findByRole('button', {name:'Manage branches'}));
  expect(await screen.findByRole('heading', {name:'Branch register'})).toBeInTheDocument();
  expect(window.location.pathname).toBe('/staff/branches');
  act(()=>{history.replaceState(null,'','/staff');window.dispatchEvent(new PopStateEvent('popstate'));});
  expect(await screen.findByRole('heading', {name:'Your workspace'})).toBeInTheDocument();
});

test('a password response arriving after sign out cannot restore the previous user', async () => {
  let finish!: (value: typeof admin) => void;
  vi.mocked(restore).mockResolvedValue(admin);
  vi.mocked(api).mockImplementation(path => path === '/api/change-password' ? new Promise(resolve => { finish = resolve; }) : Promise.resolve(undefined));
  const user = userEvent.setup();
  render(<App />);
  await user.click(await screen.findByRole('button', { name: 'Change password' }));
  await user.type(screen.getByLabelText('Current password'), 'old password');
  await user.type(screen.getByLabelText('New password'), 'a sufficiently long new password');
  await user.type(screen.getByLabelText('Confirm new password'), 'a sufficiently long new password');
  await user.click(screen.getByRole('button', { name: 'Save password' }));
  await user.click(screen.getByRole('button', { name: 'Sign out' }));
  expect(await screen.findByRole('heading', { name: 'Sign in to your workspace' })).toBeInTheDocument();
  await act(async () => finish(admin));
  expect(screen.getByRole('heading', { name: 'Sign in to your workspace' })).toBeInTheDocument();
  expect(screen.queryByRole('heading', { name: 'Your workspace' })).not.toBeInTheDocument();
});

test('restores session and offers staff creation for admin', async () => {
  vi.mocked(restore).mockResolvedValue(admin);
  render(<App />);
  expect(await screen.findByRole('heading', { name: 'Your workspace' })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Manage staff accounts' })).toBeInTheDocument();
});

test('must-change user gets password form rather than admin access', async () => {
  vi.mocked(restore).mockResolvedValue({ ...admin, must_change_password: true });
  render(<App />);
  expect(await screen.findByRole('heading', { name: 'Set your own password' })).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Manage staff accounts' })).not.toBeInTheDocument();
});

test('non-admin cannot see staff controls', async () => {
  vi.mocked(restore).mockResolvedValue({ ...admin, role: 'HR Lead' });
  render(<App />);
  await screen.findByRole('heading', { name: 'Your workspace' });
  expect(screen.queryByRole('button', { name: 'Manage staff accounts' })).not.toBeInTheDocument();
});

test('blocks duplicate login submissions while request is pending', async () => {
  vi.mocked(restore).mockResolvedValue(null);
  vi.mocked(api).mockImplementation(() => new Promise(() => {}));
  const user = userEvent.setup();
  render(<App />);
  await screen.findByRole('heading', { name: 'Sign in to your workspace' });
  await user.type(screen.getByLabelText('Email address'), 'staff@example.test');
  await user.type(screen.getByLabelText('Password', { exact: true }), 'valid password');
  await user.click(screen.getByRole('button', { name: 'Sign in' }));
  expect(screen.getByRole('button', { name: 'Signing in…' })).toBeDisabled();
  expect(api).toHaveBeenCalledTimes(1);
});

test('failed logout keeps workspace and shows error', async () => {
  vi.mocked(restore).mockResolvedValue(admin);
  vi.mocked(api).mockRejectedValue(new Error('Service unavailable. Please try again.'));
  const user = userEvent.setup();
  render(<App />);
  await screen.findByRole('heading', { name: 'Your workspace' });
  await user.click(screen.getByRole('button', { name: 'Sign out' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Service unavailable');
  expect(screen.getByRole('heading', { name: 'Your workspace' })).toBeInTheDocument();
});

test('outage during restore is visible and retryable', async () => {
  vi.mocked(restore).mockRejectedValue(new Error('Service unavailable.'));
  render(<App />);
  expect(await screen.findByRole('alert')).toHaveTextContent('Service unavailable');
  expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument();
});

test('session invalidation unmounts staff forms and returns to login', async () => {
  vi.mocked(restore).mockResolvedValue(admin);
  const user = userEvent.setup();
  render(<App />);
  await user.click(await screen.findByRole('button', { name: 'Manage staff accounts' }));
  await user.type(screen.getByLabelText('Temporary password'), 'secret not to retain');
  window.dispatchEvent(new Event('branch-session-invalid'));
  expect(await screen.findByRole('heading', { name: 'Sign in to your workspace' })).toBeInTheDocument();
  expect(screen.queryByLabelText('Temporary password')).not.toBeInTheDocument();
});

test('admin creates account without displaying or returning password', async () => {
  vi.mocked(restore).mockResolvedValue(admin);
  vi.mocked(api).mockImplementation(async (_path, method) => method === 'POST' ? {} : []);
  const user = userEvent.setup();
  render(<App />);
  await user.click(await screen.findByRole('button', { name: 'Manage staff accounts' }));
  await user.type(screen.getByLabelText('Full name'), 'New Staff');
  await user.type(screen.getByLabelText('Staff email'), 'new@example.test');
  await user.type(screen.getByLabelText('Temporary password'), 'a temporary staff password');
  await user.click(screen.getByRole('button', { name: 'Create account' }));
  await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Account created'));
  expect(screen.getByLabelText('Temporary password')).toHaveValue('');
});
