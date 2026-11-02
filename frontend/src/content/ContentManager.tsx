import {useEffect,useRef,useState} from 'react';
import {api,ApiError} from '../api';
import useResource from '../branches/useResource';
import {Feedback} from '../components/Feedback';
import {LoadState,Pagination,date} from '../membership/shared';
import type {User} from '../types';
import ContentFields from './ContentFields';
import ContentPreview from './ContentPreview';
import ContentHistory from './ContentHistory';
import {blankContent} from './types';
import type {BranchOption,ContentDocument,ContentKind,ContentPayload,Page} from './types';
import '../membership/membership.css';
import './content.css';

export default function ContentManager({user}:{user:User}){
 if(!['Content Editor','Super Admin'].includes(user.role))return <div className="membership cms"><h1 id="screen-title">Content access unavailable</h1><p role="alert">A Content Editor or Super Admin account is required.</p></div>;
 return <ContentRegister/>;
}

function ContentRegister(){
 const [selected,setSelected]=useState<string|null>(null);
 const [creating,setCreating]=useState(false);
 const [kind,setKind]=useState<ContentKind|'all'>('all');
 const [offset,setOffset]=useState(0);
 const query=useResource<Page<ContentDocument>>(`/api/content?offset=${offset}&limit=25${kind==='all'?'':`&kind=${kind}`}`);
 if(selected||creating)return <ContentEditor key={selected??'new'} id={selected} onBack={()=>{setSelected(null);setCreating(false);query.reload();}}/>;
 return <div className="membership cms"><header className="cms-heading"><div><h1 id="screen-title">Public content</h1><p>Write in English and Urdu. Review a saved draft before publishing.</p></div><button className="primary" onClick={()=>setCreating(true)}>New content</button></header>
  <div className="cms-toolbar"><label htmlFor="cms-kind-filter">Content type</label><select id="cms-kind-filter" value={kind} onChange={event=>{setKind(event.target.value as ContentKind|'all');setOffset(0);}}><option value="all">All content</option><option value="program">Programs</option><option value="event">Events</option><option value="page">Page introductions</option></select></div>
  <LoadState loading={query.loading} error={query.error} retry={query.reload}>{query.data&&<><p className="cms-help">{query.data.total} content documents</p>{query.data.items.length?<div className="cms-register">{query.data.items.map(row=><article key={row.id} className="cms-row"><div><span className="cms-kind">{row.kind}</span><h2>{row.draft.title}</h2><p lang="ur" dir="rtl">{row.draft.title_ur}</p>{row.is_demo&&<p className="cms-help">Example content · illustrative only</p>}</div><div><span className="cms-status">{row.is_published?(row.has_unpublished_changes?'Published · draft changes':'Published'):'Draft · not public'}</span><p className="cms-help">Version {row.version} · {date(row.updated_at)}</p></div><button className="secondary" aria-label={`Edit ${row.draft.title}`} onClick={()=>setSelected(row.id)}>Edit content →</button></article>)}</div>:<div className="cms-empty"><h2>No content documents yet</h2><p>Create a bilingual program, event or page introduction.</p></div>}<Pagination offset={offset} total={query.data.total} onChange={setOffset}/></>}</LoadState>
 </div>;
}

function ContentEditor({id,onBack}:{id:string|null;onBack:()=>void}){
 const [row,setRow]=useState<ContentDocument|null>(null);
 const [draft,setDraft]=useState<ContentPayload>(blankContent('program'));
 const [reason,setReason]=useState('');
 const [loading,setLoading]=useState(Boolean(id));
 const [error,setError]=useState('');
 const [busy,setBusy]=useState(false);
 const [notice,setNotice]=useState('');
 const [conflict,setConflict]=useState(false);
 const [preview,setPreview]=useState<{content:ContentPayload;version:number}|null>(null);
 const [decision,setDecision]=useState<'publish'|'unpublish'|null>(null);
 const [acknowledged,setAcknowledged]=useState(false);
 const running=useRef(false);
 const alive=useRef(true);
 const branches=useResource<BranchOption[]>('/api/content/branches');
 useEffect(()=>{alive.current=true;return()=>{alive.current=false;};},[]);
 const load=async()=>{
  if(!id)return;
  setLoading(true);setError('');
  try{const data=await api<ContentDocument>(`/api/content/${id}`);if(alive.current){setRow(data);setDraft(data.draft);setReason('');setConflict(false);setPreview(null);setDecision(null);}}
  catch(cause){if(alive.current)setError(message(cause));}
  finally{if(alive.current)setLoading(false);}
 };
 useEffect(()=>{void load();},[id]);
 const changed=Boolean(row&&JSON.stringify(draft)!==JSON.stringify(row.draft));
 const mutate=async(action:'draft'|'publish'|'unpublish')=>{
  if(running.current)return;
  if(reason.trim().length<3){setError('Enter a reason of at least 3 characters.');return;}
  running.current=true;setBusy(true);setError('');setNotice('');setConflict(false);
  try{
   const creating=!row;
   const data=await api<ContentDocument>(creating?'/api/content':`/api/content/${row.id}/${action}`,'POST',{
    reason:reason.trim(),...(row?{expected_version:row.version}:{}),...((creating||action==='draft')?{content:draft}:{}),
   });
   if(alive.current){setRow(data);setDraft(data.draft);setReason('');setPreview(null);setDecision(null);setAcknowledged(false);setNotice(action==='publish'?'Published successfully.':action==='unpublish'?'Content is no longer public.':'Draft saved.');}
  }catch(cause){if(alive.current){setError(message(cause));setConflict(cause instanceof ApiError&&cause.status===409&&cause.message.startsWith('Content changed'));}}
  finally{running.current=false;if(alive.current)setBusy(false);}
 };
 const showPreview=async()=>{
  if(!row||running.current)return;
  running.current=true;setBusy(true);setError('');
  try{const result=await api<{content:ContentPayload;version:number}>(`/api/content/${row.id}/preview`);if(alive.current)setPreview(result);}
  catch(cause){if(alive.current)setError(message(cause));}
  finally{running.current=false;if(alive.current)setBusy(false);}
 };
 if(loading)return <div className="membership cms"><h1 id="screen-title">Content editor</h1><p role="status">Loading content…</p></div>;
 if(id&&!row)return <div className="membership cms"><h1 id="screen-title">Content editor</h1><Feedback error={error}/><button className="secondary" onClick={load}>Try again</button><button className="secondary" onClick={onBack}>Back to content</button></div>;
 return <div className="membership cms"><button className="cms-back" disabled={busy} onClick={onBack}>← Back to content</button><header className="cms-heading"><div><h1 id="screen-title">{row?'Edit content':'New content'}</h1><p>{row?`Version ${row.version} · ${row.is_published?'Published':'Not public'}`:'New documents begin as private drafts.'}</p></div></header>
  {row?.is_demo&&<p className="cms-example">Example content · this record remains labelled as illustrative on the public site.</p>}
  <Feedback error={error} success={notice}/>{conflict&&<div className="cms-conflict"><p>Your input is still here. Reloading replaces it with the latest saved draft.</p><button className="secondary" disabled={busy} onClick={async()=>{if(row){setLoading(true);try{const data=await api<ContentDocument>(`/api/content/${row.id}`);if(alive.current){setRow(data);setDraft(data.draft);setConflict(false);setError('');setReason('');setPreview(null);}}catch(cause){if(alive.current)setError(message(cause));}finally{if(alive.current)setLoading(false);}}}}>Reload latest version</button></div>}
  <div className="cms-editor-grid"><section><h2>Draft</h2><p className="cms-help">Both languages are entered manually. Text is displayed as plain text.</p><form onSubmit={event=>{event.preventDefault();void mutate('draft');}}><fieldset disabled={busy}>
   {!row&&<div><label htmlFor="cms-new-kind">Content type</label><select id="cms-new-kind" value={draft.kind} onChange={event=>setDraft(blankContent(event.target.value as ContentKind))}><option value="program">Program</option><option value="event">Event</option><option value="page">Page introduction</option></select></div>}
   <ContentFields value={draft} onChange={value=>{setDraft(value);setDecision(null);}} branches={branches.data??[]} existing={Boolean(row)}/>
   {draft.kind==='event'&&branches.error&&<><p role="alert">Unable to load branch options. Your current draft is preserved.</p><button type="button" className="secondary" onClick={branches.reload}>Retry branches</button></>}
   <div><label htmlFor="cms-reason">Reason for change</label><textarea id="cms-reason" required minLength={3} maxLength={500} rows={2} value={reason} onChange={event=>setReason(event.target.value)} placeholder="Explain this draft or publication decision"/></div>
   <div className="cms-actions"><button type="submit" className="primary" disabled={busy||conflict}>{busy?'Working…':'Save draft'}</button>{row&&<button type="button" className="secondary" disabled={busy} onClick={showPreview}>Preview saved draft</button>}</div>
  </fieldset></form></section>
  <aside className="cms-public-copy"><h2>Published copy</h2><p className="cms-help">{row?.is_published?'This version is public. Saving a draft keeps this copy available.':'This document is currently hidden from the public catalogue.'}</p>{row?.published?<ContentPreview content={row.published}/>:<p>No published copy yet.</p>}
   {row&&<div className="cms-publication"><p>{changed?'Save your current changes before publishing.':row.has_unpublished_changes?'A saved draft is ready for review.':'The saved draft matches the last published copy.'}</p>{row.kind==='event'&&<p className="cms-help">Public events are visible only while their branch is Active and published.</p>}<div className="cms-actions"><button className="secondary" disabled={busy||changed||conflict} onClick={()=>{setDecision('publish');setAcknowledged(false);}}>Publish saved draft</button>{row.is_published&&<button className="secondary" disabled={busy||changed||conflict} onClick={()=>{setDecision('unpublish');setAcknowledged(false);}}>Unpublish</button>}</div>
    {decision&&<div className="cms-decision"><h3>{decision==='publish'?'Publish this saved draft?':'Remove this content from the public site?'}</h3><p>{decision==='publish'?'The saved English and Urdu copy will replace the current public version.':'The saved draft and revision history will be retained.'}</p><label className="cms-check"><input type="checkbox" checked={acknowledged} disabled={busy} onChange={event=>setAcknowledged(event.target.checked)}/>I have reviewed this publication decision.</label><p className="cms-help">Enter a reason in the draft form before confirming.</p><div className="cms-actions"><button className="primary" disabled={busy||!acknowledged||conflict} onClick={()=>mutate(decision)}>{busy?'Working…':`Confirm ${decision}`}</button><button className="secondary" disabled={busy} onClick={()=>setDecision(null)}>Cancel</button></div></div>}
   </div>}
  </aside></div>
  {preview&&<section className="cms-preview"><header className="cms-heading"><div><h2>Draft preview</h2><p className="cms-help">Saved version {preview.version} · staff only{changed?' · unsaved form changes are not included':''}</p></div><button className="secondary" onClick={()=>setPreview(null)}>Close preview</button></header><ContentPreview content={preview.content}/></section>}
  {row&&<ContentHistory key={`${row.id}:${row.version}`} id={row.id}/>}
 </div>;
}
function message(cause:unknown){return cause instanceof Error?cause.message:'Unable to complete this action. Please try again.';}
