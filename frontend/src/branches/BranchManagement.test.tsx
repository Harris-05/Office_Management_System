// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { api, ApiError } from '../api';
import BranchManagement from './BranchManagement';
import BranchActions from './BranchActions';
import type {Branch} from './types';

vi.mock('../api', async original => ({...await original<typeof import('../api')>(),api:vi.fn()}));
const user={id:'admin',name:'Admin',email:'admin@example.test',role:'Super Admin',must_change_password:false};
const row={id:'branch-one',code:'BR-000001',slug:'branch-one',name:'Test Branch',name_ur:'آزمائشی شاخ',city:'Karachi',city_ur:'کراچی',address:'Example street',address_ur:'مثالی پتہ',description:'Test details',description_ur:'تفصیل',hours:'Weekdays',hours_ur:'اوقات',status:'Forming',is_published:false,is_demo:false,version:1,lead:null,created_at:'2026-10-24T10:00:00Z',updated_at:'2026-10-24T10:00:00Z'};
const page={items:[row],total:1,offset:0,limit:25};
beforeEach(()=>vi.mocked(api).mockImplementation(async(path)=>path.includes('/audit')||path.includes('eligible-leads')?{items:[],total:0,offset:0,limit:25}:path.includes('branch-one')?row:page));
afterEach(()=>{cleanup();vi.resetAllMocks();});

test('admin can inspect a branch with lifecycle and audit controls',async()=>{
 render(<BranchManagement user={user}/>);
 await userEvent.click(await screen.findByRole('button',{name:'View Test Branch'}));
 expect(await screen.findByRole('heading',{name:'Test Branch'})).toBeInTheDocument();
 expect(screen.getByRole('button',{name:'Edit details'})).toBeVisible();
 expect(screen.getByLabelText('Next status')).toHaveValue('Active');
 expect(screen.getByRole('heading',{name:'Change history'})).toBeVisible();
});

test('an unsuccessful create keeps bilingual draft fields for retry',async()=>{
 render(<BranchManagement user={user}/>);
 await userEvent.click(screen.getByRole('button',{name:'Create branch'}));
 for(const [label,value]of [['Branch name (English)','Draft branch'],['Branch name (Urdu)','آزمائش'],['City (English)','Karachi'],['City (Urdu)','کراچی'],['Address (English)','Example street'],['Address (Urdu)','پتہ'],['Office hours (English)','Weekdays'],['Office hours (Urdu)','اوقات'],['Description (English)','Example details'],['Description (Urdu)','تفصیل']])fireEvent.change(screen.getByLabelText(label),{target:{value}});
 vi.mocked(api).mockRejectedValueOnce(new Error('Service unavailable. Please retry.'));
 await userEvent.click(screen.getByRole('button',{name:'Create branch'}));
 expect(await screen.findByRole('alert')).toHaveTextContent('Service unavailable');
 expect(screen.getByLabelText('Branch name (English)')).toHaveValue('Draft branch');
 expect(screen.getByLabelText('Branch name (Urdu)')).toHaveValue('آزمائش');
});

test('a stale edit keeps the draft and offers deliberate reload',async()=>{
 render(<BranchManagement user={user}/>);
 await userEvent.click(await screen.findByRole('button',{name:'View Test Branch'}));
 await userEvent.click(await screen.findByRole('button',{name:'Edit details'}));
 fireEvent.change(screen.getByLabelText('Branch name (English)'),{target:{value:'Unsaved name'}});
 vi.mocked(api).mockRejectedValueOnce(new ApiError(409,'This branch changed. Reload before trying again.'));
 await userEvent.click(screen.getByRole('button',{name:'Save details'}));
 expect(await screen.findByRole('alert')).toHaveTextContent('Reload');
 expect(screen.getByLabelText('Branch name (English)')).toHaveValue('Unsaved name');
 expect(screen.getByRole('button',{name:'Reload latest branch'})).toBeVisible();
});

test('branch lead sees assigned branch without administrative actions',async()=>{
 render(<BranchManagement user={{...user,role:'Branch Lead'}}/>);
 expect(screen.queryByRole('button',{name:'Create branch'})).not.toBeInTheDocument();
 await userEvent.click(await screen.findByRole('button',{name:'View Test Branch'}));
 expect(await screen.findByRole('heading',{name:'Test Branch'})).toBeInTheDocument();
 expect(screen.queryByRole('button',{name:'Edit details'})).not.toBeInTheDocument();
 expect(screen.queryByLabelText('Next status')).not.toBeInTheDocument();
});

test('other roles do not fetch internal branch data',()=>{
 render(<BranchManagement user={{...user,role:'HR Lead'}}/>);
 expect(screen.getByRole('heading',{name:'Branch access unavailable'})).toBeInTheDocument();
 expect(api).not.toHaveBeenCalled();
});

test('an unsaved lead selection remains visible when paging through lead options',async()=>{
 const first={id:'lead-a',name:'First Lead',email:'a@example.test',branch_id:null,branch_code:null};
 const second={...first,id:'lead-b',name:'Second Lead',email:'b@example.test'};
 vi.mocked(api).mockImplementation(async path=>({items:[path.includes('offset=25')?second:first],total:26,offset:path.includes('offset=25')?25:0,limit:25}));
 const mutate=vi.fn().mockResolvedValue(undefined);
 render(<BranchActions row={row as Branch} busy={false} mutate={mutate}/>);
 await screen.findByRole('option',{name:/First Lead/});
 await userEvent.selectOptions(screen.getByLabelText('Assigned Branch Lead'),'lead-a');
 await userEvent.click(screen.getByRole('button',{name:'Next leads'}));
 await screen.findByRole('option',{name:/Second Lead/});
 expect(screen.getByLabelText('Assigned Branch Lead')).toHaveValue('lead-a');
 expect(screen.getByRole('option',{name:/First Lead/})).toBeInTheDocument();
 await userEvent.click(screen.getByRole('button',{name:'Save lead'}));
 expect(mutate).toHaveBeenCalledWith('lead',{lead_id:'lead-a'});
});
