import {useState} from 'react';
import useResource from '../branches/useResource';
import {LoadState,Pagination,date} from '../membership/shared';
import ContentPreview from './ContentPreview';
import type {Page,Revision} from './types';

export default function ContentHistory({id}:{id:string}){
 const [offset,setOffset]=useState(0);
 const query=useResource<Page<Revision>>(`/api/content/${id}/history?offset=${offset}&limit=10`);
 return <section className="cms-history"><h2>Revision history</h2><LoadState loading={query.loading} error={query.error} retry={query.reload}>{query.data&&<>{query.data.items.length?<ol>{query.data.items.map(revision=><li key={revision.id}>
  <div className="cms-history-heading"><strong>Version {revision.version} · {revision.action.replaceAll('_',' ')}</strong><time dateTime={revision.created_at}>{date(revision.created_at)}</time></div>
  <p>{revision.actor?.name??'System / former staff member'} · {revision.reason}</p>
  <details><summary>View saved draft at this revision</summary><ContentPreview content={revision.snapshot.draft}/></details>
  {revision.snapshot.published&&<details><summary>View public copy at this revision ({revision.snapshot.is_published?'published':'unpublished'})</summary><ContentPreview content={revision.snapshot.published}/></details>}
 </li>)}</ol>:<p>No revisions recorded.</p>}<Pagination offset={offset} total={query.data.total} limit={10} onChange={setOffset}/></>}</LoadState></section>;
}
