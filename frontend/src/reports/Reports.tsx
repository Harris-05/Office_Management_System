import {useEffect,useState} from 'react';
import type {User} from '../types';
import useResource from '../branches/useResource';
import {BranchFilter,History,LoadState,Pagination,RecordFeedback,date,queryString,useRecord} from '../membership/shared';
import {calendarDate,formatMoney} from '../collections/display';
import type {Page,Report,Revision,Snapshot} from './types';
import '../membership/membership.css';
import './reports.css';

export default function Reports({user}:{user:User}){
  if(!['Branch Lead','Finance Reviewer','Super Admin'].includes(user.role))return <div className="membership"><h1 id="screen-title">Report access unavailable</h1><p>Weekly reports are available to Branch Leads, Finance Reviewers and Super Admins.</p></div>;
  return <Register user={user}/>;
}

function Register({user}:{user:User}){
  const [selected,setSelected]=useState<string|null>(()=>new URLSearchParams(window.location.search).get('report'));
  const [filters,setFilters]=useState({branch_id:'',status:'',from_week:'',to_week:''});
  const [applied,setApplied]=useState(filters);
  const [branchLabel,setBranchLabel]=useState('');
  const [offset,setOffset]=useState(0);
  const query=useResource<Page<Report>>(`/api/reports?${queryString({...applied,offset,limit:25})}`);
  useEffect(()=>{const listener=()=>setSelected(new URLSearchParams(window.location.search).get('report'));window.addEventListener('popstate',listener);return()=>window.removeEventListener('popstate',listener);},[]);
  const select=(id:string|null)=>{const url=new URL(window.location.href);if(id)url.searchParams.set('report',id);else url.searchParams.delete('report');window.history.pushState({},'',url);setSelected(id);};
  if(selected)return <ReportDetail key={selected} id={selected} onBack={()=>{select(null);query.reload();}}/>;
  return <div className="membership report-management">
    <header className="hr-heading"><div><h1 id="screen-title">Weekly branch reports</h1><p>Monday to Monday, Asia/Karachi. Review the week’s collections and transfers together.</p></div></header>
    <p className="report-guidance">Drafts are prepared automatically from branch registration onward. A Branch Lead can submit a closed week; Finance reviews the frozen submission.</p>
    <form className="hr-filters" onSubmit={event=>{event.preventDefault();setOffset(0);setApplied(filters);}}>
      <div><label htmlFor="report-status">Report status</label><select id="report-status" value={filters.status} onChange={event=>setFilters({...filters,status:event.target.value})}><option value="">All statuses</option>{['Draft','Submitted','Returned','Approved'].map(status=><option key={status}>{status}</option>)}</select></div>
      {user.role!=='Branch Lead'&&<BranchFilter endpoint="/api/collections/branches" value={filters.branch_id} label={branchLabel} onChange={(value,label)=>{setFilters({...filters,branch_id:value});setBranchLabel(label);}}/>}
      <div><label htmlFor="report-from">Week starting from</label><input type="date" id="report-from" value={filters.from_week} onChange={event=>setFilters({...filters,from_week:event.target.value})}/></div>
      <div><label htmlFor="report-to">Week starting through</label><input type="date" id="report-to" value={filters.to_week} onChange={event=>setFilters({...filters,to_week:event.target.value})}/></div>
      <button className="secondary" type="submit">Apply filters</button>
    </form>
    <LoadState loading={query.loading} error={query.error} retry={query.reload}>{query.data&&<>{query.data.items.length?<div className="hr-records">{query.data.items.map(row=><article className="hr-record report-register-row" key={row.id}><div><span className="hr-code">{row.branch.code}</span><h2>Week of {calendarDate(row.week_start)}</h2><p>{row.branch.name}</p></div><div><span className={`hr-status report-status-${row.status.toLowerCase()}`}>{row.status}</span><p>{row.revision_number?`Submission revision ${row.revision_number}`:'Awaiting first submission'}</p></div><button className="secondary" aria-label={`View report for ${row.branch.name}, ${row.week_start}`} onClick={()=>select(row.id)}>View report →</button></article>)}</div>:<div className="hr-empty"><h2>No weekly reports match</h2><p>Try another period or status. New branch drafts appear after the scheduled maintenance run.</p></div>}<Pagination offset={offset} total={query.data.total} onChange={setOffset}/></>}</LoadState>
  </div>;
}

type Action='narrative'|'submit'|'approve'|'return';
const labels:Record<Action,string>={narrative:'Edit narrative',submit:'Submit report',approve:'Approve report',return:'Return for correction'};

function ReportDetail({id,onBack}:{id:string;onBack:()=>void}){
  const record=useRecord<Report>(`/api/reports/${id}`);
  const {row,busy}=record;
  const [action,setAction]=useState<Action|null>(null);
  const available=(name:Action)=>row&&(name==='narrative'?row.can_edit:name==='submit'?row.can_submit:row.can_review);
  const active=action&&available(action)?action:null;
  return <div className="membership report-management"><button className="secondary back" disabled={busy} onClick={onBack}>Back to weekly reports</button>
    {!row?<><h1 id="screen-title">Weekly report</h1><LoadState loading={record.query.loading} error={record.query.error} retry={record.query.reload}>{null}</LoadState></>:<>
      <header className="hr-heading hr-detail-heading"><div><h1 id="screen-title" tabIndex={-1}>Week of {calendarDate(row.week_start)}</h1><p>{row.branch.name} · {row.branch.code}</p><p className="hr-code">{row.code}</p></div><span className={`hr-status report-status-${row.status.toLowerCase()}`}>{row.status}</span></header>
      <RecordFeedback record={record}/>
      {row.discrepancy&&<p className="report-discrepancy" role="status">Ledger changes detected. This {row.status.toLowerCase()} report retains its frozen submission figures.{row.status==='Submitted'?' Finance must return it for a fresh submission before approval.':' Approved figures remain unchanged.'}</p>}
      <section className="report-period"><h2>{row.status==='Draft'||row.status==='Returned'?'Live draft preview':'Frozen submitted figures'}</h2><p>{calendarDate(row.week_start)} 00:00 through {calendarDate(row.week_end)} 00:00, end exclusive · Asia/Karachi</p><p>Collections use the actual collection date. Transfers use the transfer date, with statuses as of the snapshot time.</p>{row.submitted_at&&<p>Submission revision {row.revision_number} · {date(row.submitted_at)}</p>}{row.approved_at&&<p>Approved {date(row.approved_at)}</p>}</section>
      {row.snapshot&&<Figures snapshot={row.snapshot}/>}
      <section className="report-narrative"><h2>Branch narrative</h2><p className="hr-message" dir="auto">{row.narrative||'No narrative supplied.'}</p></section>
      <div className="hr-actions"><a className="secondary" href={`/api/reports/${id}/export.pdf`}>Download PDF</a><a className="secondary" href={`/api/reports/${id}/export.csv`}>Download CSV</a>{!active&&(['narrative','submit','approve','return'] as Action[]).filter(available).map(name=><button key={name} className={name==='approve'||name==='submit'?'primary':'secondary'} onClick={()=>setAction(name)}>{name==='submit'&&row.revision_number?'Resubmit report':labels[name]}</button>)}</div>
      {row.can_edit&&!row.can_submit&&<p className="report-guidance">This reporting week is open. Submission becomes available after the next Monday at 00:00 Asia/Karachi.</p>}
      {active&&<Decision key={`${active}:${row.version}`} action={active} row={row} busy={busy} onCancel={()=>setAction(null)} onSave={async fields=>{if(await record.mutate(active,fields))setAction(null);}}/>}
      {row.snapshot&&<SourceDetails snapshot={row.snapshot}/>}
      <SubmissionHistory key={`revisions:${row.version}`} id={id}/>
      <History key={`audit:${row.version}`} path={`/api/reports/${id}`}/>
    </>}
  </div>;
}

function Figures({snapshot}:{snapshot:Snapshot}){
  return <section className="report-figures" aria-label="Weekly figures"><dl><div><dt>Period collections</dt><dd>{formatMoney(snapshot.collection_total)}</dd><small>{snapshot.collection_count} collections</small></div><div><dt>Period transfers · all statuses</dt><dd>{formatMoney(snapshot.transfer_total)}</dd><small>{snapshot.transfer_count} transfers</small></div></dl><dl className="report-transfer-totals">{Object.entries(snapshot.transfer_status_totals).map(([status,amount])=><div key={status}><dt>{status}</dt><dd>{formatMoney(amount)}</dd></div>)}</dl><p className="hr-help">Status subtotals reflect the snapshot time. These period figures are separate from cumulative outstanding balances.</p></section>;
}

function Decision({action,row,busy,onCancel,onSave}:{action:Action;row:Report;busy:boolean;onCancel:()=>void;onSave:(fields:object)=>Promise<void>}){
  const [narrative,setNarrative]=useState(row.narrative);
  const [reason,setReason]=useState('');
  const [acknowledge,setAcknowledge]=useState(false);
  const review=action==='approve'||action==='return';
  return <section className="hr-review"><h2>{labels[action]}</h2><form aria-busy={busy} onSubmit={event=>{event.preventDefault();void onSave({reason,...(action==='narrative'?{narrative}:{}),...(review?{acknowledge}: {})});}}><fieldset className="report-fieldset" disabled={busy}>
    {action==='narrative'&&<><label htmlFor="report-narrative">Weekly narrative (English or Urdu)</label><textarea id="report-narrative" dir="auto" maxLength={10000} rows={8} value={narrative} onChange={event=>setNarrative(event.target.value)}/></>}
    {action==='submit'&&<p>Submission freezes the displayed source revisions and narrative for Finance review.</p>}
    <label htmlFor="report-reason">Reason or review note</label><textarea id="report-reason" dir="auto" required minLength={3} maxLength={500} rows={3} value={reason} onChange={event=>setReason(event.target.value)}/>
    {review&&<label className="report-check"><input type="checkbox" checked={acknowledge} onChange={event=>setAcknowledge(event.target.checked)}/><span>I have checked this submission and its source figures. {action==='approve'?'Approval is final and freezes this report.':'The Branch Lead must submit a fresh revision.'}</span></label>}
    <button className="primary" type="submit" disabled={busy||(review&&!acknowledge)}>{busy?'Saving…':'Save decision'}</button></fieldset><button className="secondary" type="button" disabled={busy} onClick={onCancel}>Cancel</button></form></section>;
}

function SourceDetails({snapshot}:{snapshot:Snapshot}){
  return <section className="report-sources"><details><summary>Included collections ({snapshot.collection_count})</summary>{snapshot.collections.length?<ol>{snapshot.collections.map(item=><li key={item.id}><strong>{item.code} · {formatMoney(item.amount)}</strong><span>{calendarDate(item.collected_on)} · revision {item.version}</span><p dir="auto">{item.collector_name}{item.notes?` · ${item.notes}`:''}</p></li>)}</ol>:<p>No collections in this period.</p>}</details><details><summary>Included transfers ({snapshot.transfer_count})</summary>{snapshot.transfers.length?<ol>{snapshot.transfers.map(item=><li key={item.id}><strong>{item.code} · {formatMoney(item.amount)} · {item.status}</strong><span>{calendarDate(item.transferred_on)} · revision {item.version}</span><p dir="auto">{item.reference}{item.notes?` · ${item.notes}`:''}</p></li>)}</ol>:<p>No transfers in this period.</p>}</details></section>;
}

function SubmissionHistory({id}:{id:string}){
  const [offset,setOffset]=useState(0);
  const query=useResource<Page<Revision>>(`/api/reports/${id}/revisions?offset=${offset}&limit=25`);
  return <section className="hr-history"><h2>Submission revisions</h2><LoadState loading={query.loading} error={query.error} retry={query.reload}>{query.data&&<>{query.data.items.length?<ol>{query.data.items.map(item=><li key={item.id}><details><summary>Revision {item.number} · {date(item.submitted_at)}</summary><Figures snapshot={item.snapshot}/><p className="hr-message" dir="auto">{item.narrative||'No narrative supplied.'}</p><SourceDetails snapshot={item.snapshot}/></details></li>)}</ol>:<p>No submission yet. The first submission will preserve a revision here.</p>}<Pagination offset={offset} total={query.data.total} onChange={setOffset}/></>}</LoadState></section>;
}
