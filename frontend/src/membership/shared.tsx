import {useEffect, useRef, useState} from 'react';
import type {ReactNode} from 'react';
import {api, ApiError} from '../api';
import {Feedback} from '../components/Feedback';
import useResource from '../branches/useResource';
import type {BranchOption, HistoryEvent, Page} from './types';

export const canManage = (role: string) => ['Super Admin', 'HR Lead'].includes(role);
export const date = (value: string) => new Intl.DateTimeFormat('en-GB', {dateStyle:'medium', timeStyle:'short'}).format(new Date(value));
export const queryString = (fields: Record<string, string | number>) => new URLSearchParams(Object.entries(fields).filter(([,value]) => value !== '').map(([key,value]) => [key,String(value)])).toString();

export function AccessDenied() {
  return <div className="membership"><h1 id="screen-title">HR access unavailable</h1><p>Applications and members are available to HR Leads and Super Admins.</p></div>;
}

export function LoadState({loading,error,retry,children}: {loading:boolean;error:string;retry:()=>void;children:ReactNode}) {
  if (loading) return <p role="status">Loading records…</p>;
  if (error) return <><Feedback error={error}/><button className="secondary" onClick={retry}>Try again</button></>;
  return <>{children}</>;
}

export function Pagination({offset,total,limit=25,onChange}: {offset:number;total:number;limit?:number;onChange:(value:number)=>void}) {
  return <div className="hr-pagination"><button className="secondary" disabled={!offset} onClick={() => onChange(Math.max(0,offset-limit))}>Previous</button><span>{total ? `${offset+1}–${Math.min(offset+limit,total)} of ${total}` : '0 results'}</span><button className="secondary" disabled={offset+limit>=total} onClick={() => onChange(offset+limit)}>Next</button></div>;
}

export function BranchFilter({value,label,onChange,endpoint='/api/hr/branches'}: {value:string;label:string;onChange:(value:string,label:string)=>void;endpoint?:string}) {
  const [offset,setOffset] = useState(0);
  const [options,setOptions] = useState<BranchOption[]>([]);
  const query = useResource<Page<BranchOption>>(`${endpoint}?offset=${offset}&limit=25`);
  useEffect(() => {
    if (query.data) setOptions(previous => [...new Map([...previous,...query.data!.items].map(item => [item.id,item])).values()]);
  },[query.data]);
  return <div><label htmlFor="hr-branch-filter">Branch</label><select id="hr-branch-filter" value={value} onChange={event => onChange(event.target.value,event.target.selectedOptions[0]?.textContent ?? '')}><option value="">All branches</option>{value && !options.some(item => item.id===value) && <option value={value}>{label}</option>}{options.map(item => <option key={item.id} value={item.id}>{item.name} · {item.code}</option>)}</select>{query.error ? <><p role="alert">Unable to load branch options.</p><button type="button" className="secondary" onClick={query.reload}>Retry branches</button></> : query.loading ? <p className="hr-help" role="status">Loading branches…</p> : query.data && offset+25<query.data.total && <button type="button" className="secondary" onClick={() => setOffset(value => value+25)}>Load more branches</button>}</div>;
}

export function Status({value}: {value:string}) {
  return <span className={`hr-status hr-status-${value.toLowerCase()}`}>{value}</span>;
}

export function useRecord<T extends {version:number}>(path:string) {
  const query = useResource<T>(path);
  const [row,setRow] = useState<T|null>(null);
  const [busy,setBusy] = useState(false);
  const [error,setError] = useState('');
  const [notice,setNotice] = useState('');
  const [conflict,setConflict] = useState(false);
  const running = useRef(false);
  const alive = useRef(true);
  useEffect(() => {alive.current=true; return () => {alive.current=false;};},[]);
  useEffect(() => {if (query.data) setRow(query.data);},[query.data]);
  useEffect(() => {if (row) document.getElementById('screen-title')?.focus();},[Boolean(row)]);
  const mutate = async (action:string,body:object) => {
    if (running.current || !row) return false;
    running.current=true; setBusy(true); setError(''); setNotice(''); setConflict(false);
    try {
      const result = await api<T>(`${path}/${action}`,'POST',{...body,expected_version:row.version});
      if (alive.current) {setRow(result); setNotice('Saved successfully.');}
      return true;
    } catch (cause) {
      if (alive.current) {setError(cause instanceof Error ? cause.message : 'Unable to save. Please retry.'); setConflict(cause instanceof ApiError && cause.status===409);}
      return false;
    } finally {running.current=false; if (alive.current) setBusy(false);}
  };
  const reload = () => {setRow(null); setError(''); setNotice(''); setConflict(false); query.reload();};
  return {row,busy,error,notice,conflict,mutate,reload,query};
}

export function RecordFeedback({record}: {record:{error:string;notice:string;conflict:boolean;reload:()=>void}}) {
  return <><Feedback error={record.error} success={record.notice}/>{record.conflict && <div className="hr-conflict"><p>Your draft is still here. Reloading discards it and opens the latest saved record.</p><button className="secondary" onClick={record.reload}>Reload latest record</button></div>}</>;
}

export function History({path}: {path:string}) {
  const [offset,setOffset] = useState(0);
  const query = useResource<Page<HistoryEvent>>(`${path}/audit?offset=${offset}&limit=25`);
  return <section className="hr-history"><h2>Change history</h2><LoadState loading={query.loading} error={query.error} retry={query.reload}>{query.data && <>{query.data.items.length ? <ol>{query.data.items.map(item => <li key={item.id}><div className="hr-history-heading"><strong>{item.action.replaceAll('_',' ')}</strong><time dateTime={item.created_at}>{date(item.created_at)}</time></div><p dir="auto">{item.actor?.name ?? 'Former staff member'}{item.reason ? ` · ${item.reason}` : ''}</p><details><summary>View recorded changes</summary><dl>{Object.entries(item.after).filter(([key,value]) => !item.before || item.before[key]!==value).map(([key,value]) => <div key={key}><dt>{key.replaceAll('_',' ')}</dt><dd>{item.before && `${String(item.before[key] ?? 'None')} → `}{String(value ?? 'None')}</dd></div>)}</dl></details></li>)}</ol> : <p>No changes recorded yet.</p>}<Pagination offset={offset} total={query.data.total} onChange={setOffset}/></>}</LoadState></section>;
}
