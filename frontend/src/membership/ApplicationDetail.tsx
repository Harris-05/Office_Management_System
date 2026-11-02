import {useState} from 'react';
import {Submit} from '../components/Feedback';
import {date,History,LoadState,RecordFeedback,Status,useRecord} from './shared';
import type {Application} from './types';

export default function ApplicationDetail({id,onBack}: {id:string;onBack:()=>void}) {
  const record = useRecord<Application>(`/api/applications/${id}`);
  const {row,busy} = record;
  return <div className="membership"><button className="secondary back" disabled={busy} onClick={onBack}>Back to applications</button>{!row ? <><h1 id="screen-title">Application details</h1><LoadState loading={record.query.loading} error={record.query.error} retry={record.query.reload}>{null}</LoadState></> : <>
    <header className="hr-heading hr-detail-heading"><div><p className="hr-eyebrow">Volunteer application</p><h1 id="screen-title" tabIndex={-1} dir="auto">{row.name}</h1><p className="hr-email">{row.email}</p></div><Status value={row.status}/></header>
    <RecordFeedback record={record}/>
    <section className="hr-profile"><h2>Application details</h2><dl className="hr-facts"><div><dt>Preferred branch</dt><dd>{row.branch ? `${row.branch.name} · ${row.branch.code}` : 'Branch unavailable'}</dd></div><div><dt>Branch status</dt><dd>{row.branch?.status ?? 'Unavailable'}</dd></div><div><dt>Received</dt><dd>{date(row.created_at)}</dd></div><div><dt>Application expires</dt><dd>{date(row.expires_at)}</dd></div></dl><h3 dir="auto">{row.subject}</h3><p className="hr-message" dir="auto">{row.message}</p></section>
    {row.status==='Pending' ? <ReviewForm key={row.version} row={row} busy={busy} mutate={record.mutate}/> : <section className="hr-decision"><h2>{row.status==='Accepted' ? 'Application accepted' : 'Application declined'}</h2><p>{row.reviewer?.name ?? 'Former staff member'}{row.reviewed_at ? ` · ${date(row.reviewed_at)}` : ''}</p><p dir="auto">{row.reason}</p>{row.member && <a className="hr-member-link" href={`/staff/members?member=${encodeURIComponent(row.member.id)}`}>Open member {row.member.code} →</a>}</section>}
    <History key={`${id}:${row.version}`} path={`/api/applications/${id}`}/>
  </>}</div>;
}

function ReviewForm({row,busy,mutate}: {row:Application;busy:boolean;mutate:(action:string,body:object)=>Promise<boolean>}) {
  const [decision,setDecision] = useState<'Accepted'|'Declined'|null>(null);
  const [reason,setReason] = useState('');
  const [confirmed,setConfirmed] = useState(false);
  const active = row.branch?.status==='Active';
  return <section className="hr-review"><h2>Review application</h2><p>Accepting creates an Active member at the selected branch. Each email can belong to one member.</p>{!active && <p className="hr-blocked">Acceptance is unavailable while the branch is {row.branch?.status ?? 'unavailable'}. You can still decline this application.</p>}
    <div className="hr-actions"><button type="button" className={decision==='Accepted'?'primary':'secondary'} disabled={busy||!active} onClick={() => {setDecision('Accepted');setConfirmed(false);}}>Accept application</button><button type="button" className={decision==='Declined'?'primary':'secondary'} disabled={busy} onClick={() => {setDecision('Declined');setConfirmed(false);}}>Decline application</button></div>
    {decision && <form onSubmit={event => {event.preventDefault();if (confirmed && reason.trim().length>=3) void mutate('review',{decision,reason});}}><fieldset disabled={busy}><legend>{decision==='Accepted'?'Confirm acceptance':'Confirm decline'}</legend><label htmlFor="decision-reason">Decision reason</label><textarea id="decision-reason" value={reason} onChange={event => setReason(event.target.value)} required minLength={3} maxLength={500} rows={3}/><label className="hr-checkbox"><input type="checkbox" checked={confirmed} onChange={event => setConfirmed(event.target.checked)} required/><span>I confirm {decision==='Accepted'?'accepting':'declining'} {row.name}. This decision is final.</span></label><Submit busy={busy} idle={decision==='Accepted'?'Confirm acceptance':'Confirm decline'} pending="Saving decision…" disabled={!confirmed||reason.trim().length<3}/></fieldset></form>}
  </section>;
}
