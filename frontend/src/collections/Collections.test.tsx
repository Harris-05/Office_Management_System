// @vitest-environment jsdom
import {act, cleanup, fireEvent, render, screen} from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import userEvent from '@testing-library/user-event';
import {afterEach,beforeEach,expect,test,vi} from 'vitest';
import {api,ApiError} from '../api';
import Collections from './Collections';
import CollectionDetail from './CollectionDetail';
import {formatMoney,WindowStatus} from './display';

vi.mock('../api',async original => ({...await original<typeof import('../api')>(),api:vi.fn()}));
const user={id:'lead',name:'Test Lead',email:'branch@example.test',role:'Branch Lead',must_change_password:false};
const branch={id:'branch',code:'BR-000001',name:'Test branch',status:'Active'};
const row={id:'collection',code:'COL-000001',branch,amount:'10.10',currency:'PKR',collected_on:'2020-01-01',collector_name:'Test Lead',notes:'Synthetic collection',creator:{id:'lead',name:'Test Lead'},created_at:'2026-10-24T10:00:00Z',updated_at:'2026-10-24T10:00:00Z',locks_at:'2026-10-31T10:00:00Z',server_time:'2026-10-24T10:00:00Z',version:1,is_locked:false,can_edit:true};
const page=(items:unknown[])=>({items,total:items.length,offset:0,limit:25,total_amount:'10.10',currency:'PKR',server_time:row.server_time});
beforeEach(()=>vi.mocked(api).mockImplementation(async path=>path.includes('/branches')?page([branch]):path.includes('/audit')?page([]):path==='/api/collections/collection'?row:page([row])));
afterEach(()=>{cleanup();vi.resetAllMocks();vi.useRealTimers();});

test('lead creates a collection and an unchanged retry retains request reference',async()=>{
 render(<Collections user={user}/>);
 await userEvent.click(await screen.findByRole('button',{name:'New collection'}));
 fireEvent.change(screen.getByLabelText('Amount (PKR)'),{target:{value:'25.50'}});
 fireEvent.change(screen.getByLabelText('Collection date'),{target:{value:'2020-01-01'}});
 vi.mocked(api).mockRejectedValueOnce(new Error('Unable to connect. Please retry.'));
 await userEvent.click(screen.getByRole('button',{name:'Record collection'}));
 expect(await screen.findByRole('alert')).toHaveTextContent('Unable to connect');
 expect(screen.getByLabelText('Amount (PKR)')).toHaveValue('25.50');
 let resolve!:(value:unknown)=>void;
 vi.mocked(api).mockImplementationOnce(()=>new Promise(done=>{resolve=done;}));
 await userEvent.click(screen.getByRole('button',{name:'Record collection'}));
 expect(screen.getByRole('button',{name:'Recording…'})).toBeDisabled();
 const posts=vi.mocked(api).mock.calls.filter(([,method])=>method==='POST');
 expect(posts).toHaveLength(2);
 expect((posts[0][2] as {request_id:string}).request_id).toBe((posts[1][2] as {request_id:string}).request_id);
 await act(async()=>resolve(row));
 expect(await screen.findByRole('heading',{name:'COL-000001'})).toBeVisible();
});

test('stale edit preserves draft and displays original deadline',async()=>{
 render(<CollectionDetail id="collection" onBack={()=>{}}/>);
 await userEvent.click(await screen.findByRole('button',{name:'Edit collection'}));
 fireEvent.change(screen.getByLabelText('Amount (PKR)'),{target:{value:'99.99'}});
 fireEvent.change(screen.getByLabelText('Reason for change'),{target:{value:'Correct amount'}});
 vi.mocked(api).mockRejectedValueOnce(new ApiError(409,'This collection changed. Reload.'));
 await userEvent.click(screen.getByRole('button',{name:'Save collection'}));
 expect(await screen.findByRole('alert')).toHaveTextContent('Reload');
 expect(screen.getByLabelText('Amount (PKR)')).toHaveValue('99.99');
 expect(screen.getByText(/seven days after creation/i)).toBeVisible();
 expect(screen.getByRole('button',{name:'Reload latest record'})).toBeVisible();
});

test('finance has a read-only ledger without create or edit controls',async()=>{
 vi.mocked(api).mockImplementation(async path=>path.includes('/branches')?page([branch]):path.includes('/audit')?page([]):path==='/api/collections/collection'?{...row,can_edit:false}:page([{...row,can_edit:false}]));
 render(<Collections user={{...user,role:'Finance Reviewer'}}/>);
 expect(screen.queryByRole('button',{name:'New collection'})).not.toBeInTheDocument();
 await userEvent.click(await screen.findByRole('button',{name:'View COL-000001'}));
 expect(await screen.findByRole('heading',{name:'COL-000001'})).toBeVisible();
 expect(screen.queryByRole('button',{name:'Edit collection'})).not.toBeInTheDocument();
});

test('HR does not fetch financial records',()=>{
 render(<Collections user={{...user,role:'HR Lead'}}/>);
 expect(screen.getByRole('heading',{name:'Collection access unavailable'})).toBeVisible();
 expect(api).not.toHaveBeenCalled();
});

test('window indicator changes at deadline using server-relative time',()=>{
 vi.useFakeTimers();
 render(<WindowStatus row={{...row,locks_at:'2026-10-24T10:00:01Z'}}/>);
 expect(screen.getByText('Open')).toBeVisible();
 act(()=>vi.advanceTimersByTime(1000));
 expect(screen.getByText('Locked')).toBeVisible();
});

test('decimal amounts format without rounding large totals through Number',()=>{
 expect(formatMoney('9007199254740993.01')).toBe('PKR 9,007,199,254,740,993.01');
});
