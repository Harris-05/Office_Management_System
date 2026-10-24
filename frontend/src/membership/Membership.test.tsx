// @vitest-environment jsdom
import {act, cleanup, fireEvent, render, screen, waitFor} from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import userEvent from '@testing-library/user-event';
import {afterEach, beforeEach, expect, test, vi} from 'vitest';
import {api, ApiError} from '../api';
import Applications from './Applications';
import ApplicationDetail from './ApplicationDetail';
import MemberDetail from './MemberDetail';

vi.mock('../api', async original => ({...await original<typeof import('../api')>(), api: vi.fn()}));
const user = {id:'hr',name:'HR',email:'hr@example.test',role:'HR Lead',must_change_password:false};
const branch = {id:'branch',code:'BR-000001',name:'Test branch',status:'Active'};
const application = {id:'application',name:'Review Person',email:'review@example.test',subject:'Volunteer interest',message:'I would like to help.',branch,status:'Pending',version:1,created_at:'2026-10-24T10:00:00Z',expires_at:'2027-01-22T10:00:00Z',reviewed_at:null,reviewer:null,reason:null,member:null};
const member = {id:'member',code:'MEM-000001',name:application.name,email:application.email,branch,source_id:'application',status:'Active',team:'',organisational_role:'Volunteer',version:1,created_at:application.created_at,updated_at:application.created_at};
const page = (items:unknown[]) => ({items,total:items.length,offset:0,limit:25});

beforeEach(() => vi.mocked(api).mockImplementation(async path => {
  if (path.includes('/audit')) return page([]);
  if (path.includes('/hr/branches')) return page([branch]);
  if (path === '/api/applications/application') return application;
  if (path === '/api/members/member') return member;
  return page([application]);
}));
afterEach(() => {cleanup(); vi.resetAllMocks(); window.history.replaceState(null,'','/');});

test('HR opens an application from the pending review queue', async () => {
  render(<Applications user={user}/>);
  expect(screen.getByLabelText('Application status')).toHaveValue('Pending');
  await userEvent.click(await screen.findByRole('button',{name:'Review Review Person'}));
  expect(await screen.findByRole('heading',{name:'Review Person'})).toBeVisible();
  expect(screen.getByText('I would like to help.')).toBeVisible();
  expect(screen.getByRole('button',{name:'Accept application'})).toBeVisible();
});

test('acceptance requires explicit confirmation and locks duplicate requests', async () => {
  render(<ApplicationDetail id="application" onBack={() => {}}/>);
  await userEvent.click(await screen.findByRole('button',{name:'Accept application'}));
  fireEvent.change(screen.getByLabelText('Decision reason'),{target:{value:'Ready to join'}});
  expect(screen.getByRole('button',{name:'Confirm acceptance'})).toBeDisabled();
  await userEvent.click(screen.getByLabelText(/I confirm accepting/));
  let resolve!: (value:unknown) => void;
  vi.mocked(api).mockImplementationOnce(() => new Promise(done => {resolve=done;}));
  await userEvent.click(screen.getByRole('button',{name:'Confirm acceptance'}));
  expect(screen.getByRole('button',{name:'Saving decision…'})).toBeDisabled();
  expect(vi.mocked(api).mock.calls.filter(([,method]) => method === 'POST')).toHaveLength(1);
  await act(async () => resolve({...application,status:'Accepted',version:2,member}));
  expect(await screen.findByRole('link',{name:/Open member MEM-000001/})).toHaveAttribute('href','/staff/members?member=member');
  expect(screen.queryByRole('button',{name:'Accept application'})).not.toBeInTheDocument();
});

test('a stale decision preserves reason and confirmation until explicit reload', async () => {
  render(<ApplicationDetail id="application" onBack={() => {}}/>);
  await userEvent.click(await screen.findByRole('button',{name:'Decline application'}));
  fireEvent.change(screen.getByLabelText('Decision reason'),{target:{value:'Unsaved review reason'}});
  await userEvent.click(screen.getByLabelText(/I confirm declining/));
  vi.mocked(api).mockRejectedValueOnce(new ApiError(409,'This application changed. Reload.'));
  await userEvent.click(screen.getByRole('button',{name:'Confirm decline'}));
  expect(await screen.findByRole('alert')).toHaveTextContent('Reload');
  expect(screen.getByLabelText('Decision reason')).toHaveValue('Unsaved review reason');
  expect(screen.getByLabelText(/I confirm declining/)).toBeChecked();
  expect(screen.getByRole('button',{name:'Reload latest record'})).toBeVisible();
});

test('a failed member update preserves team and role drafts', async () => {
  render(<MemberDetail id="member" onBack={() => {}}/>);
  const team = await screen.findByLabelText('Team');
  fireEvent.change(team,{target:{value:'Outreach'}});
  fireEvent.change(screen.getByLabelText('Reason for change'),{target:{value:'New assignment'}});
  vi.mocked(api).mockRejectedValueOnce(new Error('Service unavailable'));
  await userEvent.click(screen.getByRole('button',{name:'Save member'}));
  expect(await screen.findByRole('alert')).toHaveTextContent('Service unavailable');
  expect(team).toHaveValue('Outreach');
  expect(screen.getByLabelText('Organisational role')).toHaveValue('Volunteer');
});

test('other roles do not fetch private application data', () => {
  render(<Applications user={{...user,role:'Branch Lead'}}/>);
  expect(screen.getByRole('heading',{name:'HR access unavailable'})).toBeVisible();
  expect(api).not.toHaveBeenCalled();
});

test('a branch filter selected from a later options page stays visible after returning from detail', async () => {
  vi.mocked(api).mockImplementation(async path => {
    if (path.includes('/audit')) return page([]);
    if (path.includes('/hr/branches')) return {items:[path.includes('offset=25') ? branch : {...branch,id:'other-branch',name:'Other branch'}],total:26,offset:0,limit:25};
    if (path === '/api/applications/application') return application;
    return page([application]);
  });
  render(<Applications user={user}/>);
  await userEvent.click(await screen.findByRole('button',{name:'Load more branches'}));
  await screen.findByRole('option',{name:/Test branch/});
  await userEvent.selectOptions(screen.getByLabelText('Branch'),'branch');
  await userEvent.click(screen.getByRole('button',{name:'Apply filters'}));
  await userEvent.click(await screen.findByRole('button',{name:'Review Review Person'}));
  await userEvent.click(await screen.findByRole('button',{name:'Back to applications'}));
  await screen.findByRole('option',{name:/Other branch/});
  expect(screen.getByLabelText('Branch')).toHaveValue('branch');
  expect(screen.getByRole('option',{name:/Test branch/})).toBeInTheDocument();
});

test('a delayed list response is ignored after navigating to another view', async () => {
  let resolve!: (value:unknown) => void;
  vi.mocked(api).mockImplementation(path => path.includes('/hr/branches') ? Promise.resolve(page([])) : new Promise(done => {resolve=done;}));
  const view = render(<Applications user={user}/>);
  await waitFor(() => expect(api).toHaveBeenCalled());
  view.unmount();
  await act(async () => resolve(page([application])));
  expect(screen.queryByText('Review Person')).not.toBeInTheDocument();
});
