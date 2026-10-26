import {useEffect,useState} from 'react';
import type {Collection} from './types';

export function formatMoney(value:string):string {
  const [whole,fraction='00']=value.split('.');
  return `PKR ${whole.replace(/\B(?=(\d{3})+(?!\d))/g,',')}.${fraction.padEnd(2,'0')}`;
}

export function pktToday():string {
  const parts=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Karachi',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date());
  const get=(type:string)=>parts.find(part=>part.type===type)?.value;
  return `${get('year')}-${get('month')}-${get('day')}`;
}

export function calendarDate(value:string):string {
  return new Intl.DateTimeFormat('en-GB',{dateStyle:'medium',timeZone:'UTC'}).format(new Date(`${value}T00:00:00Z`));
}

export function useCollectionWindow(row:Pick<Collection,'locks_at'|'server_time'|'is_locked'>):boolean {
  const [expired,setExpired]=useState(row.is_locked);
  useEffect(()=>{
    const remaining=Date.parse(row.locks_at)-Date.parse(row.server_time);
    setExpired(row.is_locked||remaining<=0);
    if(row.is_locked||remaining<=0)return;
    const timer=window.setTimeout(()=>setExpired(true),remaining);
    return()=>window.clearTimeout(timer);
  },[row.locks_at,row.server_time,row.is_locked]);
  return expired;
}

export function WindowStatus({row}:{row:Pick<Collection,'locks_at'|'server_time'|'is_locked'>}) {
  const locked=useCollectionWindow(row);
  return <span className={`hr-status ${locked?'hr-status-inactive':'hr-status-active'}`}>{locked?'Locked':'Open'}</span>;
}
