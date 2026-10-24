import {useEffect,useRef,useState} from 'react';
import {api,ApiError} from '../api';
import {Feedback} from '../components/Feedback';
import BranchEditor from './BranchEditor';
import BranchActions from './BranchActions';
import useResource from './useResource';
import type {Audit,Branch,BranchFields,Page} from './types';

const date=(value:string)=>new Intl.DateTimeFormat('en-GB',{dateStyle:'medium',timeStyle:'short'}).format(new Date(value));
export default function BranchDetail({id,admin,onBack}:{id:string;admin:boolean;onBack:()=>void}) {
 const query=useResource<Branch>(`/api/branches/${id}`);
 const [row,setRow]=useState<Branch|null>(null);const [editing,setEditing]=useState(false);
 const [busy,setBusy]=useState(false);const [error,setError]=useState('');const [notice,setNotice]=useState('');const [conflict,setConflict]=useState(false);
 const running=useRef(false);const alive=useRef(true);
 useEffect(()=>{alive.current=true;return()=>{alive.current=false;};},[]);
 useEffect(()=>{if(query.data)setRow(query.data);},[query.data]);
 useEffect(()=>{if(row)document.getElementById('screen-title')?.focus();},[row?.id]);
 const mutate=async(action:string,fields:object)=>{
  if(running.current||!row)return;running.current=true;setBusy(true);setError('');setNotice('');setConflict(false);
  try{const changed=await api<Branch>(`/api/branches/${id}/${action}`,'POST',{...fields,expected_version:row.version});if(alive.current){setRow(changed);setEditing(false);setNotice('Branch saved successfully.');}}
  catch(cause){if(alive.current){setError(cause instanceof Error?cause.message:'Unable to save this branch.');setConflict(cause instanceof ApiError&&cause.status===409);}}
  finally{running.current=false;if(alive.current)setBusy(false);}
 };
 const reload=()=>{setEditing(false);setRow(null);setError('');setNotice('');setConflict(false);query.reload();};
 return <div className="branch-management"><button className="secondary back" onClick={onBack} disabled={busy}>Back to branches</button>
  {!row?<><h1 id="screen-title">Branch details</h1>{query.error?<><Feedback error={query.error}/><button className="secondary" onClick={query.reload}>Try again</button></>:<p role="status">Loading branch…</p>}</>:<>
   <div className="branch-page-heading"><div><span className="branch-code">{row.code}</span><h1 id="screen-title" tabIndex={-1}>{row.name}</h1><p>{row.city}{row.is_demo?' · Demo record':''}</p></div><span className={`branch-status branch-status-${row.status.toLowerCase()}`}>{row.status}</span></div>
   <Feedback error={error} success={notice}/>
   {conflict&&<div className="branch-conflict"><p>Your draft is still here. Reloading discards it and opens the latest saved version.</p><button className="secondary" onClick={reload}>Reload latest branch</button></div>}
   {editing?<BranchEditor initial={row} busy={busy} onSubmit={(fields:BranchFields)=>mutate('update',fields)} onCancel={()=>setEditing(false)}/>:<>
    <section className="branch-profile" aria-labelledby="branch-profile-heading"><div className="branch-section-heading"><h2 id="branch-profile-heading">Branch profile</h2>{admin&&row.status!=='Closed'&&<button className="secondary" disabled={busy} onClick={()=>{setError('');setEditing(true);}}>Edit details</button>}</div><div className="branch-detail-languages"><div><h3>English</h3><p>{row.description}</p><dl><div><dt>Address</dt><dd>{row.address}</dd></div><div><dt>Office hours</dt><dd>{row.hours}</dd></div></dl></div><div lang="ur" dir="rtl"><h3>اردو</h3><p>{row.name_ur}، {row.city_ur}</p><p>{row.description_ur}</p><dl><div><dt>پتہ</dt><dd>{row.address_ur}</dd></div><div><dt>اوقات</dt><dd>{row.hours_ur}</dd></div></dl></div></div><dl className="branch-summary-facts"><div><dt>Branch Lead</dt><dd>{row.lead?.name??'Unassigned'}</dd></div><div><dt>Public directory</dt><dd>{row.is_published?'Published':'Unpublished'}</dd></div><div><dt>Last updated</dt><dd>{date(row.updated_at)}</dd></div></dl></section>
    {row.status==='Closed'?<p className="branch-empty">This branch is archived. Its records and history are retained.</p>:admin&&<BranchActions key={row.version} row={row} busy={busy} mutate={mutate}/>}
    <BranchHistory key={`${id}:${row.version}`} id={id}/>
   </>}
  </>}
 </div>;
}

function BranchHistory({id}:{id:string}) {
 const [offset,setOffset]=useState(0);
 const query=useResource<Page<Audit>>(`/api/branches/${id}/audit?offset=${offset}&limit=25`);
 return <section className="branch-history" aria-labelledby="branch-history-heading"><h2 id="branch-history-heading">Change history</h2>
  {query.loading?<p role="status">Loading history…</p>:query.error?<><Feedback error={query.error}/><button className="secondary" onClick={query.reload}>Retry history</button></>:query.data&&<>
   {!query.data.items.length?<p>No changes recorded yet.</p>:<ol className="branch-history-list">{query.data.items.map(item=><li key={item.id}><div className="branch-history-heading"><strong>{item.action.replaceAll('_',' ')}</strong><time dateTime={item.created_at}>{date(item.created_at)}</time></div><p>{item.actor?.name??'Former staff member'}{item.reason?` · ${item.reason}`:''}</p><details><summary>View recorded changes</summary><dl>{Object.entries(item.after).filter(([key,value])=>!item.before||item.before[key]!==value).map(([key,value])=><div key={key}><dt>{key.replaceAll('_',' ')}</dt><dd>{item.before&&<><span>{String(item.before[key]??'None')}</span><span aria-hidden="true"> → </span><span className="sr-only">changed to</span></>}<strong>{String(value??'None')}</strong></dd></div>)}</dl></details></li>)}</ol>}
   <div className="branch-pagination"><button className="secondary" disabled={!offset} onClick={()=>setOffset(value=>Math.max(0,value-25))}>Newer changes</button><span>{query.data.total} recorded changes</span><button className="secondary" disabled={offset+25>=query.data.total} onClick={()=>setOffset(value=>value+25)}>Older changes</button></div>
  </>}
 </section>;
}
