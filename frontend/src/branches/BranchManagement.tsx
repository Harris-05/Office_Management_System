import {useEffect,useRef,useState} from 'react';
import type {FormEvent} from 'react';
import {api} from '../api';
import type {User} from '../types';
import {Feedback} from '../components/Feedback';
import BranchEditor from './BranchEditor';
import BranchDetail from './BranchDetail';
import useResource from './useResource';
import {statuses} from './types';
import type {Branch,BranchFields,Page} from './types';
import './branches.css';

export default function BranchManagement({user}:{user:User}) {
 if(!['Super Admin','Branch Lead'].includes(user.role))return <><h1 id="screen-title">Branch access unavailable</h1><p>Your role does not have access to the internal branch register.</p></>;
 return <BranchRegister user={user}/>;
}
function BranchRegister({user}:{user:User}) {
 const admin=user.role==='Super Admin';
 const [search,setSearch]=useState('');const [status,setStatus]=useState('');
 const [filter,setFilter]=useState({search:'',status:''});const [offset,setOffset]=useState(0);
 const [selected,setSelected]=useState<string|null>(null);const [creating,setCreating]=useState(false);
 const [busy,setBusy]=useState(false);const [error,setError]=useState('');
 const running=useRef(false);const alive=useRef(true);
 useEffect(()=>{alive.current=true;return()=>{alive.current=false;};},[]);
 const query=useResource<Page<Branch>>(`/api/branches?${new URLSearchParams({search:filter.search,...(filter.status?{status:filter.status}:{}),offset:String(offset),limit:'25'})}`);
 const create=async(fields:BranchFields)=>{
  if(running.current)return;running.current=true;setBusy(true);setError('');
  try{const row=await api<Branch>('/api/branches','POST',fields);if(alive.current){setCreating(false);setSelected(row.id);query.reload();}}
  catch(cause){if(alive.current)setError(cause instanceof Error?cause.message:'Unable to create branch.');}
  finally{running.current=false;if(alive.current)setBusy(false);}
 };
 const back=()=>{setSelected(null);setCreating(false);setError('');query.reload();};
 if(selected)return <BranchDetail key={selected} id={selected} admin={admin} onBack={back}/>;
 if(creating)return <div className="branch-management"><h1 id="screen-title">Create branch</h1><Feedback error={error}/><BranchEditor busy={busy} onSubmit={create} onCancel={back}/></div>;
 const apply=(event:FormEvent)=>{event.preventDefault();setOffset(0);setFilter({search,status});};
 return <div className="branch-management">
  <div className="branch-page-heading"><div><h1 id="screen-title">{admin?'Branch register':'My branch'}</h1><p>{admin?'Manage local offices, responsibilities and public information.':'Your assigned branch and its recorded changes.'}</p></div>{admin&&<button className="primary" onClick={()=>{setError('');setCreating(true);}}>Create branch</button>}</div>
  {admin&&<form className="branch-filters" onSubmit={apply}><div><label htmlFor="branch-search">Search branches</label><input id="branch-search" value={search} maxLength={160} onChange={event=>setSearch(event.target.value)}/></div><div><label htmlFor="branch-status-filter">Status</label><select id="branch-status-filter" value={status} onChange={event=>setStatus(event.target.value)}><option value="">All statuses</option>{statuses.map(value=><option key={value}>{value}</option>)}</select></div><button className="secondary" type="submit">Apply filters</button></form>}
  {query.loading?<p role="status" className="branch-empty">Loading branches…</p>:query.error?<><Feedback error={query.error}/><button className="secondary" onClick={query.reload}>Try again</button></>:query.data&&<>
   <p className="branch-result-count" role="status">{query.data.total} {query.data.total===1?'branch':'branches'}</p>
   {!query.data.items.length?<div className="branch-empty"><h2>{admin?'No branches found':'No branch assigned yet'}</h2><p>{admin?'Create a branch or try different filters.':'Ask your Super Admin to assign you to a branch.'}</p></div>:<div className="branch-records">{query.data.items.map(row=><article className="branch-record" key={row.id}><div><span className="branch-code">{row.code}</span><h2>{row.name}</h2><p>{row.city}{row.is_demo?' · Demo record':''}</p></div><dl><div><dt>Status</dt><dd><span className={`branch-status branch-status-${row.status.toLowerCase()}`}>{row.status}</span></dd></div><div><dt>Public directory</dt><dd>{row.is_published?'Published':'Unpublished'}</dd></div><div><dt>Branch Lead</dt><dd>{row.lead?.name??'Unassigned'}</dd></div></dl><button className="secondary" aria-label={`View ${row.name}`} onClick={()=>setSelected(row.id)}>View branch<span aria-hidden="true"> →</span></button></article>)}</div>}
   <div className="branch-pagination"><button className="secondary" disabled={offset===0} onClick={()=>setOffset(value=>Math.max(0,value-25))}>Previous</button><span>{query.data.total?`${offset+1}–${Math.min(offset+25,query.data.total)} of ${query.data.total}`:'0 branches'}</span><button className="secondary" disabled={offset+25>=query.data.total} onClick={()=>setOffset(value=>value+25)}>Next</button></div>
  </>}
 </div>;
}
