import {useState} from 'react';
import type {User} from '../types';
import useResource from '../branches/useResource';
import {BranchFilter,LoadState,Pagination,queryString} from '../membership/shared';
import {calendarDate,formatMoney} from '../collections/display';
import TransferForm from './TransferForm';
import TransferDetail from './TransferDetail';
import type {Balances,BranchOption,Page,Transfer} from './types';
import '../membership/membership.css';
import './transfers.css';

export default function Transfers({user}:{user:User}) {
  if(!['Branch Lead','Super Admin','Finance Reviewer'].includes(user.role))return <div className="membership"><h1 id="screen-title">Transfer access unavailable</h1><p>Transfers are available to Branch Leads, Finance Reviewers and Super Admins.</p></div>;
  return user.role==='Branch Lead'?<LeadTransfers user={user}/>:<Register user={user} branch={null}/>;
}

function LeadTransfers({user}:{user:User}) {
  const scope=useResource<Page<BranchOption>>('/api/collections/branches?offset=0&limit=25');
  if(!scope.data)return <div className="membership"><h1 id="screen-title">Transfers to head office</h1><LoadState loading={scope.loading} error={scope.error} retry={scope.reload}>{null}</LoadState></div>;
  return <Register user={user} branch={scope.data.items[0]??null} reloadScope={scope.reload}/>;
}

function Register({user,branch,reloadScope}:{user:User;branch:BranchOption|null;reloadScope?:()=>void}) {
  const [selected,setSelected]=useState<string|null>(null);
  const [created,setCreated]=useState(false);
  const [creating,setCreating]=useState(false);
  const [filters,setFilters]=useState({search:'',branch_id:'',status:''});
  const [applied,setApplied]=useState(filters);
  const [branchLabel,setBranchLabel]=useState('');
  const [offset,setOffset]=useState(0);
  const query=useResource<Page<Transfer>>(`/api/transfers?${queryString({...applied,offset,limit:25})}`);
  const balances=useResource<Balances>(`/api/transfers/balances?${queryString({branch_id:applied.branch_id})}`);
  const reload=()=>{query.reload();balances.reload();};
  const isLead=user.role==='Branch Lead';
  if(selected)return <TransferDetail key={selected} id={selected} created={created} onBack={()=>{setSelected(null);setCreated(false);reload();}}/>;
  if(creating&&branch)return <TransferForm branch={branch} onBack={()=>setCreating(false)} onReloadScope={()=>{setCreating(false);reloadScope?.();reload();}} onCreated={row=>{setSelected(row.id);setCreated(true);setCreating(false);reload();}}/>;
  return <div className="membership transfer-management">
    <header className="hr-heading collection-heading"><div><h1 id="screen-title">Transfers to head office</h1><p>{isLead?(branch?`${branch.name} · ${branch.code}`:'No branch assigned yet'):'Follow branch submissions through to verified receipt.'}</p></div>{isLead&&<button className="primary" disabled={!branch||branch.status!=='Active'} onClick={()=>setCreating(true)}>New transfer</button>}</header>
    {isLead&&(!branch||branch.status!=='Active')&&<p className="hr-blocked">{!branch?'Ask your Super Admin to assign you to an Active branch before submitting transfers.':`This branch is ${branch.status}. New submissions and resubmissions require an Active branch.`}</p>}
    <LoadState loading={balances.loading} error={balances.error} retry={balances.reload}>{balances.data&&<section className="transfer-balances" aria-label="Collection and transfer balances">
      <div className="transfer-outstanding"><span>Funds not submitted</span><strong>{formatMoney(balances.data.not_submitted)}</strong><p>{formatMoney(balances.data.eligible)} is eligible now. Other unsubmitted entries become eligible after their seven-day lock.</p></div>
      <dl><div><dt>Awaiting confirmation</dt><dd>{formatMoney(balances.data.awaiting_confirmation)}</dd></div><div><dt>Confirmed received</dt><dd>{formatMoney(balances.data.confirmed_received)}</dd></div><div><dt>Total collections</dt><dd>{formatMoney(balances.data.recorded)}</dd></div></dl>
      <p className="hr-help">Balances cover all collections{applied.branch_id?' in the selected branch':' in your permitted branches'}. Search and transfer status filter the register below.</p>
    </section>}</LoadState>
    <form className="hr-filters" onSubmit={e=>{e.preventDefault();setOffset(0);setApplied(filters);}}>
      <div><label htmlFor="transfer-search">Search code or reference</label><input id="transfer-search" maxLength={160} value={filters.search} onChange={e=>setFilters({...filters,search:e.target.value})}/></div>
      <div><label htmlFor="transfer-status">Transfer status</label><select id="transfer-status" value={filters.status} onChange={e=>setFilters({...filters,status:e.target.value})}><option value="">All statuses</option>{['Submitted','Returned','Confirmed','Cancelled'].map(value=><option key={value}>{value}</option>)}</select></div>
      {!isLead&&<BranchFilter endpoint="/api/collections/branches" value={filters.branch_id} label={branchLabel} onChange={(value,label)=>{setFilters({...filters,branch_id:value});setBranchLabel(label);}}/>}
      <button className="secondary" type="submit">Apply filters</button>
    </form>
    <LoadState loading={query.loading} error={query.error} retry={query.reload}>{query.data&&<>
      {query.data.items.length?<div className="hr-records">{query.data.items.map(row=><article key={row.id} className="hr-record transfer-record"><div><span className="hr-code">{row.code}</span><h2>{formatMoney(row.amount)}</h2><p>{row.branch.name}</p><p dir="auto">{row.reference}</p></div><div><span className={`hr-status transfer-status-${row.status.toLowerCase()}`}>{row.status}</span><p>Sent {calendarDate(row.transferred_on)}</p><p>{row.items.length} collections</p></div><button className="secondary" aria-label={`View ${row.code}`} onClick={()=>setSelected(row.id)}>View transfer →</button></article>)}</div>:<div className="hr-empty"><h2>No transfers match</h2><p>{isLead?'Submit a batch after its collections have locked, or adjust the filters.':'Branch transfer submissions appear here for review. Try adjusting the filters.'}</p></div>}
      <Pagination offset={offset} total={query.data.total} onChange={setOffset}/>
    </>}</LoadState>
  </div>;
}
