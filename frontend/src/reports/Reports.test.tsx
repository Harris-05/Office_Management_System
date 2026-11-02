// @vitest-environment jsdom
import {cleanup,fireEvent,render,screen} from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import userEvent from '@testing-library/user-event';
import {afterEach,beforeEach,expect,test,vi} from 'vitest';
import {api,ApiError} from '../api';
import Reports from './Reports';

vi.mock('../api',async original=>({...await original<typeof import('../api')>(),api:vi.fn()}));
const user={id:'finance',name:'Finance',email:'finance@example.test',role:'Finance Reviewer',must_change_password:false};
const branch={id:'branch',name:'Synthetic branch',code:'BR-000001',status:'Active'};
const snapshot={collection_total:'0.03',collection_count:2,transfer_total:'0.00',transfer_count:0,collections:[],transfers:[],transfer_status_totals:{Submitted:'0.00',Returned:'0.00',Confirmed:'0.00',Cancelled:'0.00'}};
const row={id:'report',code:'RPT-BR-000001-2026-10-26',branch,week_start:'2026-10-26',week_end:'2026-11-02',status:'Submitted',version:2,narrative:'Synthetic narrative',snapshot,discrepancy:false,can_edit:false,can_submit:false,can_review:true,revision_number:1,submitted_at:'2026-11-02T00:00:00Z',approved_at:null,created_at:'2026-10-26T00:00:00Z'};
const page=(items:unknown[])=>({items,total:items.length,offset:0,limit:25});
beforeEach(()=>{window.history.replaceState({},'', '/staff/reports');vi.mocked(api).mockImplementation(async path=>path.includes('/branches')?page([branch]):path.includes('/audit')||path.includes('/revisions')?page([]):path.startsWith('/api/reports?')?page([row]):row);});
afterEach(()=>{cleanup();vi.resetAllMocks();vi.unstubAllGlobals();});

test('review requires acknowledgement and retains reason on stale snapshot',async()=>{
 render(<Reports user={user}/>);
 await userEvent.click(await screen.findByRole('button',{name:/View report/}));
 await userEvent.click(await screen.findByRole('button',{name:'Approve report'}));
 expect(screen.getByRole('button',{name:'Save decision'})).toBeDisabled();
 fireEvent.change(screen.getByLabelText('Reason or review note'),{target:{value:'Checked source snapshot'}});
 await userEvent.click(screen.getByRole('checkbox',{name:/I have checked/}));
 vi.mocked(api).mockRejectedValueOnce(new ApiError(409,'Source figures changed. Return and resubmit.'));
 await userEvent.click(screen.getByRole('button',{name:'Save decision'}));
 expect(await screen.findByRole('alert')).toHaveTextContent('Source figures changed');
 expect(screen.getByLabelText('Reason or review note')).toHaveValue('Checked source snapshot');
 expect(screen.getByRole('button',{name:'Reload latest record'})).toBeEnabled();
});

test('approved report shows frozen totals and discrepancy notice without review controls',async()=>{
 vi.mocked(api).mockImplementation(async path=>path.includes('/branches')?page([branch]):path.includes('/audit')||path.includes('/revisions')?page([]):path.startsWith('/api/reports?')?page([row]):({...row,status:'Approved',can_review:false,discrepancy:true}));
 render(<Reports user={user}/>);
 await userEvent.click(await screen.findByRole('button',{name:/View report/}));
 expect(await screen.findByText(/Ledger changes detected/)).toBeVisible();
 expect(screen.getByRole('button',{name:'Download PDF'})).toBeEnabled();
 expect(screen.queryByRole('button',{name:'Approve report'})).not.toBeInTheDocument();
});

test('restricted roles cannot load reports',()=>{
 render(<Reports user={{...user,role:'HR Lead'}}/>);
 expect(screen.getByRole('heading',{name:'Report access unavailable'})).toBeVisible();
 expect(api).not.toHaveBeenCalled();
});

test('lead edits bilingual narrative then submits a frozen revision',async()=>{
 const draft={...row,status:'Draft',version:1,revision_number:0,can_edit:true,can_submit:true,can_review:false,narrative:''};
 vi.mocked(api).mockImplementation(async path=>path.includes('/audit')||path.includes('/revisions')?page([]):path.startsWith('/api/reports?')?page([draft]):draft);
 render(<Reports user={{...user,role:'Branch Lead'}}/>);
 await userEvent.click(await screen.findByRole('button',{name:/View report/}));
 await userEvent.click(await screen.findByRole('button',{name:'Edit narrative'}));
 fireEvent.change(screen.getByLabelText('Weekly narrative (English or Urdu)'),{target:{value:'ہفتہ وار رپورٹ\nSynthetic narrative'}});
 fireEvent.change(screen.getByLabelText('Reason or review note'),{target:{value:'Weekly update'}});
 vi.mocked(api).mockResolvedValueOnce({...draft,version:2,narrative:'ہفتہ وار رپورٹ\nSynthetic narrative'});
 await userEvent.click(screen.getByRole('button',{name:'Save decision'}));
 await userEvent.click(await screen.findByRole('button',{name:'Submit report'}));
 fireEvent.change(screen.getByLabelText('Reason or review note'),{target:{value:'Ready for independent review'}});
 vi.mocked(api).mockResolvedValueOnce({...row,can_review:false});
 await userEvent.click(screen.getByRole('button',{name:'Save decision'}));
 expect(vi.mocked(api).mock.calls.filter(([,method])=>method==='POST')).toEqual([
  ['/api/reports/report/narrative','POST',{expected_version:1,reason:'Weekly update',narrative:'ہفتہ وار رپورٹ\nSynthetic narrative'}],
  ['/api/reports/report/submit','POST',{expected_version:2,reason:'Ready for independent review'}],
 ]);
 expect(await screen.findByText('Frozen submitted figures')).toBeVisible();
});

test('detail restores from the report URL and open week explains submission timing',async()=>{
 window.history.replaceState({},'', '/staff/reports?report=report');
 vi.mocked(api).mockImplementation(async path=>path.includes('/audit')||path.includes('/revisions')?page([]):path.startsWith('/api/reports?')?page([row]):({...row,status:'Draft',can_review:false,can_edit:true,can_submit:false}));
 render(<Reports user={{...user,role:'Branch Lead'}}/>);
 expect(await screen.findByText(/Submission becomes available after the next Monday/)).toBeVisible();
 expect(screen.queryByRole('button',{name:'Submit report'})).not.toBeInTheDocument();
 await userEvent.click(screen.getByRole('button',{name:'Back to weekly reports'}));
 expect(window.location.search).toBe('');
});

test('failed export keeps narrative inputs and shows a recoverable error',async()=>{
 const draft={...row,status:'Returned',can_edit:true,can_submit:true,can_review:false};
 vi.mocked(api).mockImplementation(async path=>path.includes('/audit')||path.includes('/revisions')?page([]):path.startsWith('/api/reports?')?page([draft]):draft);
 const fetcher=vi.fn().mockResolvedValue({ok:false,status:422,json:async()=>({detail:'Unsupported PDF character. Use CSV.'})});
 vi.stubGlobal('fetch',fetcher);
 render(<Reports user={{...user,role:'Branch Lead'}}/>);
 await userEvent.click(await screen.findByRole('button',{name:/View report/}));
 await userEvent.click(await screen.findByRole('button',{name:'Edit narrative'}));
 fireEvent.change(screen.getByLabelText('Weekly narrative (English or Urdu)'),{target:{value:'Preserve my narrative'}});
 await userEvent.click(screen.getByRole('button',{name:'Download PDF'}));
 expect(await screen.findByRole('alert')).toHaveTextContent('Unsupported PDF character');
 expect(screen.getByLabelText('Weekly narrative (English or Urdu)')).toHaveValue('Preserve my narrative');
 expect(fetcher).toHaveBeenCalledWith('/api/reports/report/export.pdf',expect.objectContaining({credentials:'same-origin'}));
});

test('expired export session notifies shell without navigating away',async()=>{
 const invalid=vi.fn();window.addEventListener('branch-session-invalid',invalid);
 vi.stubGlobal('fetch',vi.fn().mockResolvedValue({ok:false,status:401,json:async()=>({detail:'Session expired.'})}));
 render(<Reports user={user}/>);
 await userEvent.click(await screen.findByRole('button',{name:/View report/}));
 await userEvent.click(screen.getByRole('button',{name:'Download CSV'}));
 expect(await screen.findByRole('alert')).toHaveTextContent('Session expired');
 expect(invalid).toHaveBeenCalledTimes(1);
 expect(window.location.pathname).toBe('/staff/reports');
 window.removeEventListener('branch-session-invalid',invalid);
});

test('oversized returned period clearly labels the last submission and blocks resubmit',async()=>{
 window.history.replaceState({},'', '/staff/reports?report=report');
 vi.mocked(api).mockImplementation(async path=>path.includes('/audit')||path.includes('/revisions')?page([]):path.startsWith('/api/reports?')?page([row]):({...row,status:'Returned',can_review:false,can_edit:true,can_submit:false,preview_unavailable:true,preview_unavailable_reason:'Live source count exceeds report limit.',snapshot_basis:'last_submission',discrepancy:true}));
 render(<Reports user={{...user,role:'Branch Lead'}}/>);
 expect(await screen.findByRole('heading',{name:'Last submitted figures'})).toBeVisible();
 expect(screen.getByText('Live source count exceeds report limit.')).toBeVisible();
 expect(screen.queryByRole('button',{name:'Resubmit report'})).not.toBeInTheDocument();
 expect(screen.queryByText(/This reporting week is open/)).not.toBeInTheDocument();
});
