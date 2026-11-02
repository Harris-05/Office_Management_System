// @vitest-environment jsdom
import {act,cleanup,fireEvent,render,screen} from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import userEvent from '@testing-library/user-event';
import {afterEach,beforeEach,expect,test,vi} from 'vitest';
import {api,ApiError} from '../api';
import Transfers from './Transfers';
import TransferDetail from './TransferDetail';
import {selectedTotal} from './types';

vi.mock('../api',async original=>({...await original<typeof import('../api')>(),api:vi.fn()}));
const user={id:'lead',name:'Test Lead',email:'branch@example.test',role:'Branch Lead',must_change_password:false};
const branch={id:'branch',name:'Test branch',code:'BR-000001',status:'Active'};
const collection={id:'collection',code:'COL-000001',amount:'10.10',collected_on:'2020-01-01',collector_name:'Test Lead'};
const row={id:'transfer',code:'TRF-000001',branch,amount:'10.10',currency:'PKR',transferred_on:'2026-01-01',reference:'SYNTHETIC',notes:'',status:'Submitted',version:1,creator:{id:'lead',name:'Test Lead'},reviewer:null,created_at:'2026-10-27T10:00:00Z',updated_at:'2026-10-27T10:00:00Z',confirmed_at:null,items:[{...collection,collection_id:'collection',collection_version:1}],can_confirm:false,can_return:false,can_cancel:true,can_resubmit:false};
const page=(items:unknown[])=>({items,total:items.length,offset:0,limit:25});
const balances={recorded:'10.10',not_submitted:'10.10',eligible:'10.10',awaiting_confirmation:'0.00',confirmed_received:'0.00',currency:'PKR'};
beforeEach(()=>vi.mocked(api).mockImplementation(async path=>path.includes('/branches')?page([branch]):path.includes('/balances')?balances:path.includes('/eligible')?page([collection]):path.includes('/audit')?page([]):path==='/api/transfers/transfer'?row:page([row])));
afterEach(()=>{cleanup();vi.resetAllMocks();});

test('lead submits a selected batch, preserves retry ID and disables duplicate requests',async()=>{
 render(<Transfers user={user}/>);
 await userEvent.click(await screen.findByRole('button',{name:'New transfer'}));
 await userEvent.click(await screen.findByRole('checkbox',{name:/COL-000001/}));
 fireEvent.change(screen.getByLabelText('Transfer reference'),{target:{value:'DEPOSIT-123'}});
 await userEvent.click(screen.getByRole('checkbox',{name:/I have sent/}));
 vi.mocked(api).mockRejectedValueOnce(new Error('Connection interrupted. Retry safely.'));
 await userEvent.click(screen.getByRole('button',{name:'Submit transfer'}));
 expect(await screen.findByRole('alert')).toHaveTextContent('Connection interrupted');
 expect(screen.getByLabelText('Transfer reference')).toHaveValue('DEPOSIT-123');
 let resolve!:(value:unknown)=>void;
 vi.mocked(api).mockImplementationOnce(()=>new Promise(done=>{resolve=done;}));
 await userEvent.click(screen.getByRole('button',{name:'Submit transfer'}));
 expect(screen.getByRole('button',{name:'Submitting…'})).toBeDisabled();
 const posts=vi.mocked(api).mock.calls.filter(([,method])=>method==='POST');
 expect(posts).toHaveLength(2);
 expect((posts[0][2] as {request_id:string}).request_id).toBe((posts[1][2] as {request_id:string}).request_id);
 expect(posts[1][2]).toMatchObject({expected_branch_id:'branch',collection_ids:['collection']});
 await act(async()=>resolve(row));
 expect(await screen.findByRole('heading',{name:'TRF-000001'})).toBeVisible();
});

test('Finance confirms actual receipt with an explicit acknowledgement',async()=>{
 vi.mocked(api).mockImplementation(async path=>path.includes('/audit')?page([]):{...row,can_confirm:true,can_return:true,can_cancel:false});
 render(<TransferDetail id="transfer" onBack={()=>{}}/>);
 await userEvent.click(await screen.findByRole('button',{name:'Confirm receipt'}));
 expect(screen.getByRole('button',{name:'Save decision'})).toBeDisabled();
 await userEvent.click(screen.getByRole('checkbox',{name:/I have verified/}));
 fireEvent.change(screen.getByLabelText('Reason or review note'),{target:{value:'Receipt verified against bank reference'}});
 vi.mocked(api).mockResolvedValueOnce({...row,status:'Confirmed',can_confirm:false,can_return:false,can_cancel:false});
 await userEvent.click(screen.getByRole('button',{name:'Save decision'}));
 expect(vi.mocked(api).mock.calls.find(([,method])=>method==='POST')).toEqual(['/api/transfers/transfer/confirm','POST',{expected_version:1,reason:'Receipt verified against bank reference'}]);
 expect(await screen.findByText('Confirmed',{selector:'.hr-status'})).toBeVisible();
});

test('stale decision preserves reason and offers explicit reload',async()=>{
 render(<TransferDetail id="transfer" onBack={()=>{}}/>);
 await userEvent.click(await screen.findByRole('button',{name:'Cancel transfer'}));
 fireEvent.change(screen.getByLabelText('Reason or review note'),{target:{value:'Keep this draft'}});
 vi.mocked(api).mockRejectedValueOnce(new ApiError(409,'This transfer changed.'));
 await userEvent.click(screen.getByRole('button',{name:'Save decision'}));
 expect(await screen.findByRole('alert')).toHaveTextContent('This transfer changed');
 expect(screen.getByLabelText('Reason or review note')).toHaveValue('Keep this draft');
 expect(screen.getByRole('button',{name:'Reload latest record'})).toBeEnabled();
});

test('Admin is read-only and HR has no financial interface',async()=>{
 const view=render(<Transfers user={{...user,role:'Super Admin'}}/>);
 await screen.findByText('Funds not submitted');
 expect(screen.queryByRole('button',{name:'New transfer'})).not.toBeInTheDocument();
 view.unmount();vi.mocked(api).mockClear();
 render(<Transfers user={{...user,role:'HR Lead'}}/>);
 expect(screen.getByRole('heading',{name:'Transfer access unavailable'})).toBeVisible();
 expect(api).not.toHaveBeenCalled();
});

test('no eligible collections explains the seven-day wait',async()=>{
 vi.mocked(api).mockImplementation(async path=>path.includes('/branches')?page([branch]):path.includes('/balances')?balances:page([]));
 render(<Transfers user={user}/>);
 await userEvent.click(await screen.findByRole('button',{name:'New transfer'}));
 expect(await screen.findByText('No collections are ready for transfer')).toBeVisible();
 expect(screen.getByRole('button',{name:'Submit transfer'})).toBeDisabled();
});

test('selected totals retain exact cents beyond floating point integer precision',()=>{
 expect(selectedTotal([{amount:'9999999999.99'},{amount:'0.01'}])).toBe('10000000000.00');
 expect(selectedTotal([{amount:'0.10'},{amount:'0.20'}])).toBe('0.30');
});

test('paging eligible collections preserves selection without submitting the form',async()=>{
 vi.mocked(api).mockImplementation(async path=>path.includes('/branches')?page([branch]):path.includes('/balances')?balances:path.includes('/eligible')?{...page([collection]),total:26}:page([]));
 render(<Transfers user={user}/>);
 await userEvent.click(await screen.findByRole('button',{name:'New transfer'}));
 await userEvent.click(await screen.findByRole('checkbox',{name:/COL-000001/}));
 fireEvent.change(screen.getByLabelText('Transfer reference'),{target:{value:'READY-TO-SEND'}});
 await userEvent.click(screen.getByRole('checkbox',{name:/I have sent/}));
 await userEvent.click(screen.getByRole('button',{name:'Next'}));
 expect(vi.mocked(api).mock.calls.filter(([,method])=>method==='POST')).toHaveLength(0);
 expect(screen.getByText('1 of 100 collections selected')).toBeVisible();
});

test('retrying a failed collection page does not submit an acknowledged transfer',async()=>{
 let pageFailed=false;
 vi.mocked(api).mockImplementation(async path=>{
   if(path.includes('/branches'))return page([branch]);
   if(path.includes('/balances'))return balances;
   if(path.includes('/eligible')){
     if(path.includes('offset=25')&&!pageFailed){pageFailed=true;throw new Error('Temporary page failure');}
     return {...page([collection]),total:26};
   }
   return page([]);
 });
 render(<Transfers user={user}/>);
 await userEvent.click(await screen.findByRole('button',{name:'New transfer'}));
 await userEvent.click(await screen.findByRole('checkbox',{name:/COL-000001/}));
 fireEvent.change(screen.getByLabelText('Transfer reference'),{target:{value:'READY-TO-SEND'}});
 await userEvent.click(screen.getByRole('checkbox',{name:/I have sent/}));
 await userEvent.click(screen.getByRole('button',{name:'Next'}));
 await userEvent.click(await screen.findByRole('button',{name:'Try again'}));
 expect(vi.mocked(api).mock.calls.filter(([,method])=>method==='POST')).toHaveLength(0);
 expect(screen.getByText('1 of 100 collections selected')).toBeVisible();
});

test('reloading a terminal transfer after a conflict closes the obsolete decision form',async()=>{
 vi.mocked(api).mockImplementation(async path=>path.includes('/audit')?page([]):{...row,can_confirm:true,can_return:true,can_cancel:false});
 render(<TransferDetail id="transfer" onBack={()=>{}}/>);
 await userEvent.click(await screen.findByRole('button',{name:'Confirm receipt'}));
 fireEvent.change(screen.getByLabelText('Reason or review note'),{target:{value:'Keep this review'}});
 await userEvent.click(screen.getByRole('checkbox',{name:/I have verified/}));
 vi.mocked(api).mockRejectedValueOnce(new ApiError(409,'Another reviewer already confirmed this transfer.'));
 await userEvent.click(screen.getByRole('button',{name:'Save decision'}));
 await screen.findByRole('alert');
 vi.mocked(api).mockImplementation(async path=>path.includes('/audit')?page([]):{...row,status:'Confirmed',can_confirm:false,can_return:false,can_cancel:false,can_resubmit:false});
 await userEvent.click(screen.getByRole('button',{name:'Reload latest record'}));
 expect(await screen.findByText('Confirmed',{selector:'.hr-status'})).toBeVisible();
 expect(screen.queryByLabelText('Reason or review note')).not.toBeInTheDocument();
 expect(screen.queryByRole('button',{name:'Save decision'})).not.toBeInTheDocument();
});
