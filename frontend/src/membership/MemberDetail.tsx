import {useState} from 'react';
import {Submit} from '../components/Feedback';
import {date,History,LoadState,RecordFeedback,Status,useRecord} from './shared';
import type {Member} from './types';

export default function MemberDetail({id,onBack}: {id:string;onBack:()=>void}) {
  const record = useRecord<Member>(`/api/members/${id}`);
  const {row,busy} = record;
  return <div className="membership"><button className="secondary back" disabled={busy} onClick={onBack}>Back to members</button>{!row ? <><h1 id="screen-title">Member details</h1><LoadState loading={record.query.loading} error={record.query.error} retry={record.query.reload}>{null}</LoadState></> : <>
    <header className="hr-heading hr-detail-heading"><div><span className="hr-code">{row.code}</span><h1 id="screen-title" tabIndex={-1} dir="auto">{row.name}</h1><p className="hr-email">{row.email}</p></div><Status value={row.status}/></header><RecordFeedback record={record}/>
    <section className="hr-profile"><h2>Member profile</h2><dl className="hr-facts"><div><dt>Branch</dt><dd>{row.branch.name} · {row.branch.code}</dd></div><div><dt>Branch status</dt><dd>{row.branch.status}</dd></div><div><dt>Joined</dt><dd>{date(row.created_at)}</dd></div><div><dt>Last updated</dt><dd>{date(row.updated_at)}</dd></div></dl><p className="hr-help">Name, email, member ID and branch are retained from registration. This record does not provide staff login access.</p>{row.source_id ? <p>Source application is retained until its expiry.</p> : <p>The source application is no longer available; membership is retained.</p>}</section>
    <MemberForm key={row.version} row={row} busy={busy} mutate={record.mutate}/><History key={`${id}:${row.version}`} path={`/api/members/${id}`}/>
  </>}</div>;
}

function MemberForm({row,busy,mutate}: {row:Member;busy:boolean;mutate:(action:string,body:object)=>Promise<boolean>}) {
  const [team,setTeam] = useState(row.team);
  const [role,setRole] = useState(row.organisational_role);
  const [status,setStatus] = useState(row.status);
  const [reason,setReason] = useState('');
  return <section className="hr-review"><h2>Organisation details</h2><p>Team and role describe membership responsibilities. They do not change system permissions.</p><form onSubmit={event => {event.preventDefault();void mutate('update',{team,organisational_role:role,status,reason});}}><fieldset disabled={busy}><legend className="sr-only">Edit member</legend><div className="hr-edit-grid"><div><label htmlFor="member-team">Team</label><input id="member-team" maxLength={80} value={team} onChange={event => setTeam(event.target.value)}/></div><div><label htmlFor="member-role">Organisational role</label><input id="member-role" maxLength={100} required value={role} onChange={event => setRole(event.target.value)}/></div><div><label htmlFor="member-status">Status</label><select id="member-status" value={status} onChange={event => setStatus(event.target.value as Member['status'])}><option>Active</option><option>Inactive</option></select></div></div><label htmlFor="member-reason">Reason for change</label><textarea id="member-reason" minLength={3} maxLength={500} required rows={3} value={reason} onChange={event => setReason(event.target.value)}/><p className="hr-help">Give an operational reason without unnecessary personal details.</p><Submit busy={busy} idle="Save member" pending="Saving member…" disabled={!role.trim()||reason.trim().length<3}/></fieldset></form></section>;
}
