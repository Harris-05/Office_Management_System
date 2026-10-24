import { useEffect, useState } from 'react';
import type { Language } from './content';

interface Published { id: string; slug: string; is_demo: boolean; description: string; description_ur: string }
export interface Branch extends Published { name: string; name_ur: string; city: string; city_ur: string; address: string; address_ur: string; hours: string; hours_ur: string }
export interface Program extends Published { title: string; title_ur: string; audience: string; audience_ur: string }
export interface PublicEvent extends Published { title: string; title_ur: string; branch_id: string; starts_at: string; ends_at: string }
export interface Catalogue { branches: Branch[]; programs: Program[]; events: PublicEvent[] }

export function localized<T>(row: T, field: keyof T, language: Language): string {
 return String(language === 'ur' ? row[`${String(field)}_ur` as keyof T] || row[field] : row[field]);
}
export function eventDate(date: string, language: Language, time = false) {
 return new Intl.DateTimeFormat(language === 'ur' ? 'ur-PK' : 'en-GB', {
  timeZone: 'Asia/Karachi', ...(time ? {hour:'numeric',minute:'2-digit'} as const : {day:'numeric',month:'short',year:'numeric'} as const),
 }).format(new Date(date));
}
export function useCatalogue() {
 const [data, setData] = useState<Catalogue | null>(null);
 const [error, setError] = useState(false);
 const [attempt, setAttempt] = useState(0);
 useEffect(() => {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 15000);
  let current = true;
  setError(false);
  fetch('/api/public/catalog', {signal:controller.signal, credentials:'omit'})
   .then(async response => { if (!response.ok) throw new Error('Catalogue unavailable'); return response.json() as Promise<Catalogue>; })
   .then(result => {if (current) setData(result);})
   .catch(() => {if (current) setError(true);})
   .finally(() => clearTimeout(timeout));
  return () => {current=false; clearTimeout(timeout); controller.abort();};
 }, [attempt]);
 return {data,error,retry:() => {setData(null);setAttempt(value=>value+1);}};
}
