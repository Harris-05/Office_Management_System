import {useState} from 'react';
import {date,History,LoadState,RecordFeedback,useRecord} from '../membership/shared';
import {calendarDate,formatMoney} from '../collections/display';
import {MetadataFields} from './TransferForm';
import type {Transfer,TransferMetadata} from './types';

type Action='confirm'|'return'|'cancel'|'resubmit';
const labels:Record<Action,string>={confirm:'Confirm receipt',return:'Return for correction',cancel:'Cancel transfer',resubmit:'Resubmit transfer'};

export default function TransferDetail({id,onBack,created=false}:{id:string;onBack:()=>void;created?:boolean}) {
  const record=useRecord<Transfer>(`/api/transfers/${id}`);
  const [action,setAction]=useState<Action|null>(null);
  const {row,busy}=record;
  const activeAction=action&&row?.[`can_${action}`]?action:null;
  return <div className="membership transfer-management">
    <button className="secondary back" disabled={busy} onClick={onBack}>Back to transfers</button>
    {!row?<><h1 id="screen-title">Transfer details</h1><LoadState loading={record.query.loading} error={record.query.error} retry={record.query.reload}>{null}</LoadState></>:<>
      <header className="hr-heading hr-detail-heading"><div><p className="hr-eyebrow">Transfer to head office</p><h1 id="screen-title" tabIndex={-1}>{row.code}</h1><p>{row.branch.name} · {row.branch.code}</p></div><span className={`hr-status transfer-status-${row.status.toLowerCase()}`}>{row.status}</span></header>
      <RecordFeedback record={{...record,notice:record.notice||(created?'Transfer submitted. Finance confirmation is pending.':'')}}/>
      <section className="hr-profile">
        <h2 className="transfer-amount">{formatMoney(row.amount)}</h2>
        <dl className="hr-facts"><div><dt>Transfer date</dt><dd>{calendarDate(row.transferred_on)}</dd></div><div><dt>Reference</dt><dd dir="auto">{row.reference}</dd></div><div><dt>Submitted by</dt><dd>{row.creator?.name??'Former staff member'}</dd></div><div><dt>Created</dt><dd>{date(row.created_at)}</dd></div><div><dt>Latest Finance reviewer</dt><dd>{row.reviewer?.name??'Awaiting review'}</dd></div><div><dt>Receipt confirmed</dt><dd>{row.confirmed_at?date(row.confirmed_at):'Not confirmed'}</dd></div></dl>
        {row.notes&&<><h3>Notes</h3><p className="hr-message" dir="auto">{row.notes}</p></>}
        <p className="transfer-guidance">{row.status==='Confirmed'?'Finance has verified receipt. This transfer is final and read-only.':row.status==='Returned'?'The collections have been released. Resubmission requires the entire original batch to remain available.':row.status==='Cancelled'?'This transfer is final. Its collections are available for another transfer unless reserved elsewhere.':'These collections are reserved. Submitted money is shown separately from confirmed receipts.'}</p>
      </section>
      <section className="transfer-items"><h2>Included collections</h2><p>The fixed batch contains {row.items.length} collection{row.items.length===1?'':'s'}.</p><dl>{row.items.map(item=><div key={item.collection_id}><dt>{item.code}<span>Collected {calendarDate(item.collected_on)} · revision {item.collection_version}</span></dt><dd>{formatMoney(item.amount)}</dd></div>)}</dl></section>
      {!activeAction&&<div className="hr-actions">{(['confirm','return','resubmit','cancel'] as Action[]).filter(name=>row[`can_${name}`]).map(name=><button key={name} className={name==='confirm'||name==='resubmit'?'primary':'secondary'} onClick={()=>setAction(name)}>{labels[name]}</button>)}</div>}
      {activeAction&&<DecisionForm key={`${activeAction}:${row.version}`} action={activeAction} row={row} busy={busy} onCancel={()=>setAction(null)} onSave={async fields=>{if(await record.mutate(activeAction,fields))setAction(null);}}/>}
      <History key={`${row.id}:${row.version}`} path={`/api/transfers/${row.id}`}/>
    </>}
  </div>;
}

function DecisionForm({action,row,busy,onCancel,onSave}:{action:Action;row:Transfer;busy:boolean;onCancel:()=>void;onSave:(fields:object)=>Promise<void>}) {
  const [reason,setReason]=useState('');
  const [acknowledged,setAcknowledged]=useState(false);
  const [fields,setFields]=useState<TransferMetadata>({transferred_on:row.transferred_on,reference:row.reference,notes:row.notes});
  return <section className="hr-review"><h2>{labels[action]}</h2><form aria-busy={busy} onSubmit={e=>{e.preventDefault();void onSave({...(action==='resubmit'?fields:{}),reason});}}>
    <fieldset className="transfer-fieldset" disabled={busy}>
      {action==='resubmit'&&<MetadataFields value={fields} onChange={setFields}/>}
      <label htmlFor="transfer-reason">Reason or review note</label><textarea id="transfer-reason" required minLength={3} maxLength={500} rows={3} dir="auto" value={reason} onChange={e=>setReason(e.target.value)}/>
      {action==='confirm'&&<label className="transfer-check"><input type="checkbox" checked={acknowledged} onChange={e=>setAcknowledged(e.target.checked)}/><span>I have verified that head office received {formatMoney(row.amount)} against this transfer reference. Confirmation is final.</span></label>}
      <button type="submit" className="primary" disabled={busy||(action==='confirm'&&!acknowledged)}>{busy?'Saving…':'Save decision'}</button>
    </fieldset><button type="button" className="secondary" disabled={busy} onClick={onCancel}>Keep current status</button>
  </form></section>;
}
