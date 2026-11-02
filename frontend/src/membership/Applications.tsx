import {useState} from 'react';
import type {User} from '../types';
import useResource from '../branches/useResource';
import ApplicationDetail from './ApplicationDetail';
import {AccessDenied,BranchFilter,canManage,date,LoadState,Pagination,queryString,Status} from './shared';
import type {Application,Page} from './types';
import './membership.css';

export default function Applications({user}: {user:User}) {
  return canManage(user.role) ? <ApplicationQueue/> : <AccessDenied/>;
}

function ApplicationQueue() {
  const [selected,setSelected] = useState<string|null>(null);
  const [search,setSearch] = useState('');
  const [status,setStatus] = useState('Pending');
  const [branch,setBranch] = useState('');
  const [branchLabel,setBranchLabel] = useState('');
  const [applied,setApplied] = useState({search:'',status:'Pending',branch_id:''});
  const [offset,setOffset] = useState(0);
  const query = useResource<Page<Application>>(`/api/applications?${queryString({...applied,offset,limit:25})}`);
  if (selected) return <ApplicationDetail key={selected} id={selected} onBack={() => {setSelected(null); query.reload();}}/>;
  return <div className="membership"><header className="hr-heading"><h1 id="screen-title">Volunteer applications</h1><p>Review people ready to contribute to a branch. Acceptance creates their member record.</p></header>
    <form className="hr-filters" onSubmit={event => {event.preventDefault();setOffset(0);setApplied({search,status,branch_id:branch});}}>
      <div><label htmlFor="hr-search">Search name or email</label><input id="hr-search" maxLength={160} value={search} onChange={event => setSearch(event.target.value)}/></div>
      <div><label htmlFor="application-status">Application status</label><select id="application-status" value={status} onChange={event => setStatus(event.target.value)}>{['Pending','Accepted','Declined','All'].map(value => <option key={value}>{value}</option>)}</select></div>
      <BranchFilter value={branch} label={branchLabel} onChange={(value,label) => {setBranch(value);setBranchLabel(label);}}/><button type="submit" className="secondary">Apply filters</button>
    </form>
    <LoadState loading={query.loading} error={query.error} retry={query.reload}>{query.data && <><p className="hr-result-count">{query.data.total} applications</p>{query.data.items.length ? <div className="hr-records">{query.data.items.map(item => <article className="hr-record" key={item.id}><div><h2 dir="auto">{item.name}</h2><p className="hr-email">{item.email}</p><p>{item.branch?.name ?? 'Branch unavailable'}</p></div><div><Status value={item.status}/><p className="hr-meta">Received {date(item.created_at)}</p></div><button className="secondary" aria-label={`Review ${item.name}`} onClick={() => setSelected(item.id)}>Review application →</button></article>)}</div> : <div className="hr-empty"><h2>No applications match</h2><p>New volunteer submissions appear here. Try another status or clear your filters.</p></div>}<Pagination offset={offset} total={query.data.total} onChange={setOffset}/></>}</LoadState>
  </div>;
}
