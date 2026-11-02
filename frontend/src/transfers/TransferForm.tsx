import {useRef,useState} from 'react';
import {api,ApiError} from '../api';
import useResource from '../branches/useResource';
import {Feedback} from '../components/Feedback';
import {LoadState,Pagination} from '../membership/shared';
import {calendarDate,formatMoney,pktToday} from '../collections/display';
import {selectedTotal} from './types';
import type {BranchOption,EligibleCollection,Page,Transfer,TransferMetadata} from './types';

export function MetadataFields({value,onChange}:{value:TransferMetadata;onChange:(value:TransferMetadata)=>void}) {
  return <div className="hr-edit-grid">
    <div><label htmlFor="transfer-date">Transfer date</label><input id="transfer-date" type="date" required max={pktToday()} value={value.transferred_on} onChange={e=>onChange({...value,transferred_on:e.target.value})}/></div>
    <div><label htmlFor="transfer-reference">Transfer reference</label><input id="transfer-reference" required minLength={3} maxLength={120} dir="auto" value={value.reference} onChange={e=>onChange({...value,reference:e.target.value})}/></div>
    <div className="transfer-wide"><label htmlFor="transfer-notes">Notes (optional)</label><textarea id="transfer-notes" rows={3} maxLength={1000} dir="auto" value={value.notes} onChange={e=>onChange({...value,notes:e.target.value})}/></div>
  </div>;
}

export default function TransferForm({branch,onCreated,onBack,onReloadScope}:{branch:BranchOption;onCreated:(row:Transfer)=>void;onBack:()=>void;onReloadScope:()=>void}) {
  const [offset,setOffset]=useState(0);
  const query=useResource<Page<EligibleCollection>>(`/api/transfers/eligible?offset=${offset}&limit=25`);
  const [selected,setSelected]=useState<Record<string,EligibleCollection>>({});
  const [fields,setFields]=useState<TransferMetadata>({transferred_on:pktToday(),reference:'',notes:''});
  const [acknowledged,setAcknowledged]=useState(false);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  const [conflict,setConflict]=useState(false);
  const running=useRef(false);
  const request=useRef({serialized:'',id:''});
  const entries=Object.values(selected);
  const toggle=(row:EligibleCollection)=>setSelected(previous=>{
    const next={...previous};if(next[row.id])delete next[row.id];else if(Object.keys(next).length<100)next[row.id]=row;return next;
  });
  const submit=async()=>{
    if(running.current||!acknowledged||!entries.length)return;
    const payload={...fields,expected_branch_id:branch.id,collection_ids:Object.keys(selected).sort()};
    const serialized=JSON.stringify(payload);
    if(request.current.serialized!==serialized)request.current={serialized,id:crypto.randomUUID()};
    running.current=true;setBusy(true);setError('');setConflict(false);
    try{onCreated(await api<Transfer>('/api/transfers','POST',{...payload,request_id:request.current.id}));}
    catch(cause){setError(cause instanceof Error?cause.message:'Unable to submit this transfer. Please retry.');setConflict(cause instanceof ApiError&&cause.status===409);}
    finally{running.current=false;setBusy(false);}
  };
  return <div className="membership transfer-management">
    <h1 id="screen-title">New transfer</h1><p>{branch.name} · {branch.code}</p>
    <p className="transfer-guidance">Select whole collection entries whose seven-day editing window has ended. Record money you have already sent to head office; Finance will verify receipt.</p>
    <Feedback error={error}/>{conflict&&<div className="hr-conflict"><p>Your selection and details are still here. Reloading discards this draft and checks the current branch and available collections.</p><button className="secondary" onClick={onReloadScope}>Reload branch and collections</button></div>}
    <form onSubmit={e=>{e.preventDefault();void submit();}} aria-busy={busy}>
      <fieldset disabled={busy} className="transfer-fieldset">
        <legend>Collections to transfer</legend>
        <LoadState loading={query.loading} error={query.error} retry={query.reload}>{query.data&&<>
          {query.data.items.length?<div className="transfer-selection">{query.data.items.map(row=><label className="transfer-option" key={row.id}>
            <input type="checkbox" checked={Boolean(selected[row.id])} disabled={!selected[row.id]&&entries.length>=100} onChange={()=>toggle(row)}/>
            <span><strong>{row.code}</strong><span dir="auto">{row.collector_name}</span><span>Collected {calendarDate(row.collected_on)}</span></span><strong>{formatMoney(row.amount)}</strong>
          </label>)}</div>:<div className="hr-empty"><h2>No collections are ready for transfer</h2><p>Collections become eligible seven days after creation. Entries already reserved or confirmed in another transfer are excluded.</p></div>}
          <Pagination offset={offset} total={query.data.total} onChange={setOffset}/>
        </>}</LoadState>
        <div className="transfer-selected" aria-live="polite"><span>{entries.length} of 100 collections selected</span><strong>{formatMoney(selectedTotal(entries))}</strong></div>
        {entries.length>0&&<details><summary>Review all selected collections</summary><ul>{entries.map(row=><li key={row.id}>{row.code} · {formatMoney(row.amount)} <button type="button" className="secondary" aria-label={`Remove ${row.code}`} onClick={()=>toggle(row)}>Remove</button></li>)}</ul></details>}
        <MetadataFields value={fields} onChange={setFields}/>
        <label className="transfer-check"><input type="checkbox" checked={acknowledged} onChange={e=>setAcknowledged(e.target.checked)}/><span>I have sent this amount to head office and checked the selected collections and transfer reference.</span></label>
        <button className="primary" disabled={!entries.length||!acknowledged||busy} type="submit">{busy?'Submitting…':'Submit transfer'}</button>
      </fieldset>
      <button type="button" className="secondary" disabled={busy} onClick={onBack}>Back to transfers</button>
    </form>
  </div>;
}
