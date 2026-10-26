import {useEffect,useRef,useState} from 'react';
import {api,ApiError} from '../api';
import type {User} from '../types';
import useResource from '../branches/useResource';
import {BranchFilter,LoadState,Pagination,queryString} from '../membership/shared';
import {Feedback} from '../components/Feedback';
import CollectionForm from './CollectionForm';
import CollectionDetail from './CollectionDetail';
import {calendarDate,formatMoney,WindowStatus} from './display';
import type {BranchOption,Collection,CollectionFields,CollectionPage,Page} from './types';
import '../membership/membership.css';
import './collections.css';

export default function Collections({user}:{user:User}) {
  if(!['Branch Lead','Super Admin','Finance Reviewer'].includes(user.role))return <div className="membership"><h1 id="screen-title">Collection access unavailable</h1><p>Collections are available to Branch Leads, Finance Reviewers and Super Admins.</p></div>;
  return user.role==='Branch Lead'?<LeadRegistry user={user}/>:<CollectionRegister user={user} branch={null}/>;
}

function LeadRegistry({user}:{user:User}) {
  const query=useResource<Page<BranchOption>>('/api/collections/branches?offset=0&limit=25');
  if(!query.data)return <div className="membership"><h1 id="screen-title">Offline collections</h1><LoadState loading={query.loading} error={query.error} retry={query.reload}>{null}</LoadState></div>;
  return <CollectionRegister user={user} branch={query.data.items[0]??null} reloadScope={query.reload}/>;
}

function CollectionRegister({user,branch,reloadScope}:{user:User;branch:BranchOption|null;reloadScope?:()=>void}) {
  const [selected,setSelected]=useState<string|null>(null);
  const [creating,setCreating]=useState(false);
  const [created,setCreated]=useState(false);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  const [conflict,setConflict]=useState(false);
  const [filters,setFilters]=useState({search:'',branch_id:'',window:'All',from_date:'',to_date:''});
  const [applied,setApplied]=useState(filters);
  const [branchLabel,setBranchLabel]=useState('');
  const [offset,setOffset]=useState(0);
  const request=useRef({serialized:'',id:''});
  const running=useRef(false);
  const alive=useRef(true);
  useEffect(()=>{alive.current=true;return()=>{alive.current=false;};},[]);
  const query=useResource<CollectionPage>(`/api/collections?${queryString({...applied,offset,limit:25})}`);
  const isLead=user.role==='Branch Lead';
  const field=(key:keyof typeof filters,value:string)=>setFilters(previous=>({...previous,[key]:value}));
  const save=async(fields:CollectionFields)=>{
    if(running.current)return;
    const payload={...fields,expected_branch_id:branch?.id};
    const serialized=JSON.stringify(payload);
    if(request.current.serialized!==serialized)request.current={serialized,id:crypto.randomUUID()};
    running.current=true;setBusy(true);setError('');setConflict(false);
    try{
      const row=await api<Collection>('/api/collections','POST',{...payload,request_id:request.current.id});
      if(alive.current){setSelected(row.id);setCreating(false);setCreated(true);request.current={serialized:'',id:''};query.reload();}
    }catch(cause){if(alive.current){setError(cause instanceof Error?cause.message:'Unable to record this collection. Please retry.');setConflict(cause instanceof ApiError&&cause.status===409);}}
    finally{running.current=false;if(alive.current)setBusy(false);}
  };
  if(selected)return <CollectionDetail key={selected} id={selected} created={created} onBack={()=>{setSelected(null);setCreated(false);query.reload();}}/>;
  if(creating)return <div className="membership collection-management"><h1 id="screen-title">New collection</h1><p>{branch?.name} · {branch?.code}</p><p className="collection-lock-help">This entry locks seven days after creation, regardless of its collection date.</p><Feedback error={error}/>{conflict&&<div className="hr-conflict"><p>Your draft is still here. Reloading branch details discards it and starts with the current assignment.</p><button className="secondary" onClick={reloadScope}>Reload branch details</button></div>}<CollectionForm collector={user.name} busy={busy} onSubmit={save} onCancel={()=>{setCreating(false);setError('');request.current={serialized:'',id:''};}}/></div>;
  return <div className="membership collection-management">
    <header className="hr-heading collection-heading"><div><h1 id="screen-title">Offline collections</h1><p>{isLead?(branch?`${branch.name} · ${branch.code}`:'No branch assigned yet'):'Read-only overview across the branch network.'}</p></div>{isLead&&<button className="primary" disabled={!branch||branch.status!=='Active'} onClick={()=>setCreating(true)}>New collection</button>}</header>
    {isLead&&(!branch||branch.status!=='Active')&&<p className="hr-blocked">{!branch?'Ask your Super Admin to assign you to a branch before recording collections.':`This branch is ${branch.status}. It must be Active to create or edit collections.`}</p>}
    <form className="hr-filters collection-filters" onSubmit={event=>{event.preventDefault();setOffset(0);setApplied(filters);}}>
      <div><label htmlFor="collection-search">Search code or collector</label><input id="collection-search" maxLength={160} value={filters.search} onChange={event=>field('search',event.target.value)}/></div>
      <div><label htmlFor="collection-window">Editing window</label><select id="collection-window" value={filters.window} onChange={event=>field('window',event.target.value)}><option>All</option><option>Open</option><option>Locked</option></select></div>
      {!isLead&&<BranchFilter endpoint="/api/collections/branches" value={filters.branch_id} label={branchLabel} onChange={(value,label)=>{field('branch_id',value);setBranchLabel(label);}}/>}
      <div><label htmlFor="collection-from">Collected from</label><input id="collection-from" type="date" value={filters.from_date} onChange={event=>field('from_date',event.target.value)}/></div>
      <div><label htmlFor="collection-to">Collected to</label><input id="collection-to" type="date" value={filters.to_date} onChange={event=>field('to_date',event.target.value)}/></div><button className="secondary" type="submit">Apply filters</button>
    </form>
    <LoadState loading={query.loading} error={query.error} retry={query.reload}>{query.data&&<>
      <div className="collection-total"><div><span>Recorded total</span><strong>{formatMoney(query.data.total_amount)}</strong><p>Across all entries matching these filters.</p></div><span>{query.data.total} collections</span></div>
      {query.data.items.length?<div className="hr-records">{query.data.items.map(row=><article className="hr-record collection-record" key={row.id}><div><span className="hr-code">{row.code}</span><h2>{formatMoney(row.amount)}</h2><p>{row.branch.name}</p><p dir="auto">{row.collector_name}</p></div><div><WindowStatus row={row}/><p>Collected {calendarDate(row.collected_on)}</p></div><button className="secondary" aria-label={`View ${row.code}`} onClick={()=>setSelected(row.id)}>View collection →</button></article>)}</div>:<div className="hr-empty"><h2>No collections match</h2><p>{isLead?'Record an offline collection or adjust your filters.':'Collections recorded by branch leads appear here. Try adjusting your filters.'}</p></div>}
      <Pagination offset={offset} total={query.data.total} onChange={setOffset}/>
    </>}</LoadState>
  </div>;
}
