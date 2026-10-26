import {useState} from 'react';
import {date,History,LoadState,RecordFeedback,useRecord} from '../membership/shared';
import CollectionForm from './CollectionForm';
import {calendarDate,formatMoney,useCollectionWindow,WindowStatus} from './display';
import type {Collection} from './types';

export default function CollectionDetail({id,onBack,created=false}:{id:string;onBack:()=>void;created?:boolean}) {
  const record=useRecord<Collection>(`/api/collections/${id}`);
  const [editing,setEditing]=useState(false);
  const {row,busy}=record;
  return <div className="membership collection-management"><button className="secondary back" disabled={busy} onClick={onBack}>Back to collections</button>{!row?<><h1 id="screen-title">Collection details</h1><LoadState loading={record.query.loading} error={record.query.error} retry={record.query.reload}>{null}</LoadState></>:<DetailContent row={row} busy={busy} editing={editing} setEditing={setEditing} record={record} created={created}/>}</div>;
}

function DetailContent({row,busy,editing,setEditing,record,created}:{row:Collection;busy:boolean;editing:boolean;setEditing:(value:boolean)=>void;record:ReturnType<typeof useRecord<Collection>>;created:boolean}) {
  const locked=useCollectionWindow(row);
  const canEdit=row.can_edit&&!locked;
  return <>
    <header className="hr-heading hr-detail-heading"><div><p className="hr-eyebrow">Offline collection</p><h1 id="screen-title" tabIndex={-1}>{row.code}</h1><p>{row.branch.name} · {row.branch.code}</p></div><WindowStatus row={row}/></header>
    <RecordFeedback record={{...record,notice:record.notice||(created?'Collection recorded successfully.':'')}}/>
    <section className="hr-profile"><div className="collection-profile-heading"><h2>{formatMoney(row.amount)}</h2>{canEdit&&!editing&&<button className="secondary" onClick={()=>setEditing(true)}>Edit collection</button>}</div>
      <dl className="hr-facts"><div><dt>Collection date</dt><dd>{calendarDate(row.collected_on)}</dd></div><div><dt>Collected by</dt><dd dir="auto">{row.collector_name}</dd></div><div><dt>Created</dt><dd>{date(row.created_at)}</dd></div><div><dt>Edit deadline</dt><dd>{date(row.locks_at)}</dd></div><div><dt>Recorded by</dt><dd>{row.creator?.name??'Former staff member'}</dd></div><div><dt>Branch status</dt><dd>{row.branch.status}</dd></div></dl>
      <p className="collection-lock-help">Editing locks seven days after creation. Changing the collection date does not extend this deadline.</p>
      {row.notes&&<><h3>Notes</h3><p className="hr-message" dir="auto">{row.notes}</p></>}
      {!canEdit&&<p className="hr-help">{locked?'The editing window has ended. This entry is read-only.':'Only the assigned lead of an Active branch can edit an open collection.'}</p>}
    </section>
    {editing&&<section className="hr-review"><h2>Correct collection details</h2><CollectionForm key={row.version} initial={row} collector={row.collector_name} busy={busy} locked={!canEdit} onCancel={()=>setEditing(false)} onSubmit={async(fields,reason)=>{if(await record.mutate('update',{...fields,reason}))setEditing(false);}}/></section>}
    <History key={`${row.id}:${row.version}`} path={`/api/collections/${row.id}`}/>
  </>;
}
