import {useState} from 'react';
import {Feedback} from '../components/Feedback';
import useResource from './useResource';
import {transitions} from './types';
import type {Branch,BranchStatus,Lead,Page} from './types';

export default function BranchActions({row,busy,mutate}:{row:Branch;busy:boolean;mutate:(action:string,body:object)=>Promise<void>}) {
 const [next,setNext]=useState<BranchStatus>(transitions[row.status][0]);
 const [reason,setReason]=useState('');const [confirmed,setConfirmed]=useState(false);
 return <div className="branch-actions-grid">
  <section className="branch-action-panel"><h2>Branch status</h2><p>Pausing or closing removes the branch from the public directory. Closing also releases its lead assignment.</p><form onSubmit={event=>{event.preventDefault();if(next==='Closed'&&!confirmed)return;void mutate('status',{status:next,reason});}}><fieldset disabled={busy}><legend className="sr-only">Change branch status</legend><label htmlFor="next-status">Next status</label><select id="next-status" value={next} onChange={event=>{setNext(event.target.value as BranchStatus);setConfirmed(false);}}>{transitions[row.status].map(value=><option key={value}>{value}</option>)}</select><label htmlFor="status-reason">Reason for change</label><textarea id="status-reason" value={reason} onChange={event=>setReason(event.target.value)} required minLength={3} maxLength={500} rows={3}/>{next==='Closed'&&<label className="branch-checkbox"><input type="checkbox" checked={confirmed} onChange={event=>setConfirmed(event.target.checked)} required/><span>Close {row.name} permanently. This cannot be reopened.</span></label>}<button className="primary" disabled={busy||reason.trim().length<3||(next==='Closed'&&!confirmed)}>Change status</button></fieldset></form></section>
  <LeadAssignment row={row} busy={busy} mutate={mutate}/>
  <section className="branch-action-panel branch-publication"><div><h2>Public directory</h2><p>{row.status!=='Active'?'Activate this branch before publishing it.':row.is_published?'This branch is visible on the public website.':'This branch is Active but not published. Publishing also makes it available for new volunteer interests.'}</p></div><button className="secondary" disabled={busy||row.status!=='Active'} onClick={()=>void mutate('publication',{is_published:!row.is_published})}>{row.is_published?'Unpublish branch':'Publish branch'}</button></section>
 </div>;
}

function LeadAssignment({row,busy,mutate}:{row:Branch;busy:boolean;mutate:(action:string,body:object)=>Promise<void>}) {
 const [leadId,setLeadId]=useState(row.lead?.id??'');const [offset,setOffset]=useState(0);
 const [selectedLead,setSelectedLead]=useState<{id:string;name:string}|null>(row.lead);
 const [search,setSearch]=useState('');const [applied,setApplied]=useState('');
 const query=useResource<Page<Lead>>(`/api/branches/eligible-leads?${new URLSearchParams({offset:String(offset),limit:'25',search:applied})}`);
 return <section className="branch-action-panel"><h2>Branch Lead</h2><p>Assign an active Branch Lead account. Each lead can manage one branch.</p>
  <form className="branch-lead-search" onSubmit={event=>{event.preventDefault();setOffset(0);setApplied(search);}}><label htmlFor="lead-search">Find a lead by name or email</label><div><input id="lead-search" value={search} onChange={event=>setSearch(event.target.value)} maxLength={160}/><button type="submit" className="secondary" disabled={busy}>Search</button></div></form>
  {query.loading?<p role="status">Loading eligible leads…</p>:query.error?<><Feedback error={query.error}/><button className="secondary" onClick={query.reload}>Retry leads</button></>:query.data&&<>
   <form onSubmit={event=>{event.preventDefault();void mutate('lead',{lead_id:leadId||null});}}><label htmlFor="assigned-lead">Assigned Branch Lead</label><select id="assigned-lead" disabled={busy} value={leadId} onChange={event=>{const id=event.target.value;setLeadId(id);setSelectedLead(query.data?.items.find(item=>item.id===id)??(row.lead?.id===id?row.lead:null));}}><option value="">Unassigned</option>{selectedLead&&!query.data.items.some(item=>item.id===selectedLead.id)&&<option value={selectedLead.id}>{selectedLead.name} · selected lead</option>}{query.data.items.map(item=><option key={item.id} value={item.id} disabled={Boolean(item.branch_id&&item.branch_id!==row.id)}>{item.name} · {item.email}{item.branch_id&&item.branch_id!==row.id?` · assigned to ${item.branch_code}`:''}</option>)}</select><button className="primary" disabled={busy||leadId===(row.lead?.id??'')}>Save lead</button></form>
   <div className="branch-pagination"><button className="secondary" disabled={!offset||busy} onClick={()=>setOffset(value=>Math.max(0,value-25))}>Previous leads</button><span>{query.data.total} leads</span><button className="secondary" disabled={offset+25>=query.data.total||busy} onClick={()=>setOffset(value=>value+25)}>Next leads</button></div>
  </>}
 </section>;
}
