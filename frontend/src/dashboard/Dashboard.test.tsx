// @vitest-environment jsdom
import {cleanup, fireEvent, render, screen, waitFor} from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import userEvent from '@testing-library/user-event';
import {afterEach, beforeEach, expect, test, vi} from 'vitest';
import {api} from '../api';
import Dashboard from './Dashboard';

vi.mock('../api', async original => ({...await original<typeof import('../api')>(), api: vi.fn()}));
const user = {id: 'finance', name: 'Test Finance', email: 'finance@example.test', role: 'Finance Reviewer', must_change_password: false};
const data = {
  live_collections: {count: 3, amount: '9007199254740993.01', currency: 'PKR'},
  monthly: [{month: '2020-01', count: 1, amount: '0.10'}, {month: '2020-02', count: 2, amount: '1234.76'}],
  reconciliation: {recorded: '1234.86', not_submitted: '1234.86', eligible: '0.10', awaiting_confirmation: '0.00', confirmed_received: '0.00', currency: 'PKR'},
  reports: {statuses: {Draft: 1, Submitted: 2, Returned: 0, Approved: 1}, approved_collection_total: '100.10', approved_transfer_total: '50.00', approved_discrepancies: 1},
  outstanding: {items: [{id: 'collection', code: 'COL-000001', branch: {id: 'branch', code: 'BR-000001', name: 'Test branch', status: 'Active'}, amount: '0.10', collected_on: '2020-01-31', locks_at: '2026-10-31T10:00:00Z', eligible: true}], total: 26, offset: 0, limit: 25},
  server_time: '2026-11-02T00:00:00Z',
};
beforeEach(() => {vi.mocked(api).mockImplementation(async path => path.includes('/branches') ? {items: [], total: 0} : data);});
afterEach(() => {cleanup(); vi.resetAllMocks(); vi.unstubAllGlobals();});

test('displays exact money, chart table, approved discrepancy and cumulative meaning', async () => {
  render(<Dashboard user={user}/>);
  expect(await screen.findByText('PKR 9,007,199,254,740,993.01')).toBeVisible();
  await userEvent.click(screen.getByText('View monthly figures'));
  expect(screen.getByRole('table', {name: 'Monthly collection figures'})).toHaveTextContent('1,234.76');
  expect(screen.getByText(/independent of the collection date filter/i)).toBeVisible();
  expect(screen.getByText(/1 approved report differs/i)).toBeVisible();
  expect(screen.getByRole('table', {name: 'Unallocated collections'})).toHaveTextContent('Eligible');
});

test('applies business date filters, resets paging and exports applied scope', async () => {
  const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify({detail: 'Too many records. Narrow the date range.'}), {status: 422, headers: {'Content-Type': 'application/json'}}));
  vi.stubGlobal('fetch', fetcher);
  render(<Dashboard user={user}/>);
  await screen.findByText('PKR 9,007,199,254,740,993.01');
  await userEvent.click(screen.getByRole('button', {name: 'Next'}));
  await waitFor(() => expect(api).toHaveBeenCalledWith(expect.stringContaining('offset=25')));
  fireEvent.change(screen.getByLabelText('Collected from'), {target: {value: '2020-02-01'}});
  fireEvent.change(screen.getByLabelText('Collected to'), {target: {value: '2020-02-29'}});
  await userEvent.click(screen.getByRole('button', {name: 'Apply filters'}));
  await waitFor(() => expect(api).toHaveBeenCalledWith(expect.stringContaining('date_from=2020-02-01&date_to=2020-02-29&offset=0')));
  await userEvent.click(screen.getByRole('button', {name: 'Export collections CSV'}));
  expect(await screen.findByRole('alert')).toHaveTextContent('Narrow the date range');
  expect(fetcher).toHaveBeenCalledWith('/api/dashboard/export.csv?date_from=2020-02-01&date_to=2020-02-29', expect.objectContaining({credentials: 'same-origin'}));
});

test.each(['HR Lead', 'Content Editor'])('%s never fetches dashboard data', role => {
  vi.mocked(api).mockClear();
  render(<Dashboard user={{...user, role}}/>);
  expect(screen.getByRole('heading', {name: 'Dashboard access unavailable'})).toBeVisible();
  expect(api).not.toHaveBeenCalled();
});

test('failed dashboard fetch supports retry and empty monthly data is explained', async () => {
  vi.mocked(api).mockImplementation(async path => {
    if (path.includes('/branches')) return {items: [], total: 0};
    throw new Error('Synthetic connection failure');
  });
  render(<Dashboard user={user}/>);
  expect(await screen.findByRole('alert')).toHaveTextContent('Synthetic connection failure');
  vi.mocked(api).mockResolvedValue({...data, monthly: [], outstanding: {...data.outstanding, items: [], total: 0}});
  await userEvent.click(screen.getByRole('button', {name: 'Try again'}));
  expect(await screen.findByText('No collections match this date range.')).toBeVisible();
  expect(screen.getByText('No unallocated collections in this branch scope.')).toBeVisible();
});
