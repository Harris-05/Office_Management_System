import {useState} from 'react';
import type {User} from '../types';
import useResource from '../branches/useResource';
import MemberDetail from './MemberDetail';
import {AccessDenied,BranchFilter,canManage,LoadState,Pagination,queryString,Status} from './shared';
import type {Member,Page} from './types';
import './membership.css';

export default function Members({user}: {user:User}) {
  return canManage(user.role) ? <MemberRegister/> : <AccessDenied/>;
}

function MemberRegister() {
  const [selected,setSelected] = useState<string|null>(() => new URLSearchParams(window.location.search).get('member'));
  const [filters,setFilters] = useState({search:'',status:'',branch_id:'',team:'',organisational_role:''});
  const [branchLabel,setBranchLabel] = useState('');
  const [applied,setApplied] = useState(filters);
  const [offset,setOffset] = useState(0);
  const query = useResource<Page<Member>>(`/api/members?${queryString({...applied,offset,limit:25})}`);
  const field = (key:keyof typeof filters,value:string) => setFilters(previous => ({...previous,[key]:value}));
  if (selected) return <MemberDetail key={selected} id={selected} onBack={() => {setSelected(null);window.history.replaceState(null,'','/staff/members');query.reload();}}/>;
  return <div className="membership"><header className="hr-heading"><h1 id="screen-title">Member register</h1><p>People accepted into the branch network. Membership is separate from staff login access.</p></header>
    <form className="hr-filters hr-member-filters" onSubmit={event => {event.preventDefault();setOffset(0);setApplied(filters);}}>
      <div><label htmlFor="member-search">Search name, email or member ID</label><input id="member-search" maxLength={160} value={filters.search} onChange={event => field('search',event.target.value)}/></div>
      <div><label htmlFor="member-filter-status">Member status</label><select id="member-filter-status" value={filters.status} onChange={event => field('status',event.target.value)}><option value="">All statuses</option><option>Active</option><option>Inactive</option></select></div>
      <BranchFilter value={filters.branch_id} label={branchLabel} onChange={(value,label) => {field('branch_id',value);setBranchLabel(label);}}/>
      <div><label htmlFor="member-filter-team">Team filter</label><input id="member-filter-team" value={filters.team} maxLength={80} onChange={event => field('team',event.target.value)}/></div>
      <div><label htmlFor="member-filter-role">Organisational role filter</label><input id="member-filter-role" value={filters.organisational_role} maxLength={100} onChange={event => field('organisational_role',event.target.value)}/></div><button className="secondary" type="submit">Apply filters</button>
    </form>
    <LoadState loading={query.loading} error={query.error} retry={query.reload}>{query.data && <><p className="hr-result-count">{query.data.total} members</p>{query.data.items.length ? <div className="hr-records">{query.data.items.map(item => <article key={item.id} className="hr-record"><div><span className="hr-code">{item.code}</span><h2 dir="auto">{item.name}</h2><p className="hr-email">{item.email}</p><p>{item.branch.name}</p></div><div><Status value={item.status}/><p>{item.organisational_role}{item.team ? ` · ${item.team}` : ''}</p></div><button className="secondary" aria-label={`View member ${item.name}`} onClick={() => setSelected(item.id)}>View member →</button></article>)}</div> : <div className="hr-empty"><h2>No members match</h2><p>Accept a volunteer application to create a member, or adjust your filters.</p></div>}<Pagination offset={offset} total={query.data.total} onChange={setOffset}/></>}</LoadState>
  </div>;
}
