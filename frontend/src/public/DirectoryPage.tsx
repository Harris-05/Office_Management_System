import { useEffect, useRef, useState } from 'react';
import { content } from './content';
import type { Language } from './content';
import { eventDate, localized, useCatalogue } from './catalogue';
import { publicCopy } from './publicCopy';
import CatalogueState from './CatalogueState';

export default function DirectoryPage({page,language}:{page:'branches'|'events'|'programs';language:Language}) {
 const {data,error,retry}=useCatalogue();
 const [search,setSearch]=useState('');
 const [branch,setBranch]=useState('');
 const [period,setPeriod]=useState('upcoming');
 const fragmentHandled=useRef(false);
 useEffect(()=>{
  if(!data||fragmentHandled.current||!window.location.hash)return;
  let slug: string;
  try {slug=decodeURIComponent(window.location.hash.slice(1));} catch {fragmentHandled.current=true;return;}
  const event=data.events.find(row=>row.slug===slug);
  if(page==='events'&&event&&Date.parse(event.ends_at)<Date.now()&&period!=='past'){setPeriod('past');return;}
  const target=document.getElementById(slug);
  if(target){target.scrollIntoView({behavior:'instant',block:'start'});fragmentHandled.current=true;}
 },[data,page,period]);
 const copy=publicCopy[language];
 const base=content[language][page];
 const text=search.trim().toLocaleLowerCase();
 const branches=data?.branches.filter(row=>[row.name,row.name_ur,row.city,row.city_ur].some(value=>value.toLocaleLowerCase().includes(text))) ?? [];
 const events=data?.events.filter(row=>(!branch||row.branch_id===branch) && (period==='past'?new Date(row.ends_at).getTime()<Date.now():new Date(row.ends_at).getTime()>=Date.now()) && [row.title,row.title_ur].some(value=>value.toLocaleLowerCase().includes(text))).sort((a,b)=>period==='past'?Date.parse(b.starts_at)-Date.parse(a.starts_at):Date.parse(a.starts_at)-Date.parse(b.starts_at)) ?? [];
 const empty=data && (page==='branches'?branches.length===0:page==='events'?events.length===0:data.programs.length===0);
 const demo=data?.[page].some(row=>row.is_demo);
 const reset=()=>{setSearch('');setBranch('');setPeriod('upcoming');};
 return <>
  <section className="public-intro home-section"><h1 data-home-reveal>{base.title}</h1><p data-home-reveal>{page==='programs'?copy.takePartBody:content[language][page].body}</p></section>
  <section className="directory-section home-section" aria-labelledby="directory-title">
   <div className="directory-heading"><h2 id="directory-title" data-home-reveal>{copy[page]}</h2>{demo && <p className="demo-notice"><strong>{copy.demo}.</strong> {copy.demoNote}</p>}</div>
   {page!=='programs' && <div className="directory-filters">
    <label htmlFor="directory-search">{page==='branches'?copy.searchBranches:copy.searchEvents}<input id="directory-search" type="search" value={search} onChange={event=>setSearch(event.target.value)} /></label>
    {page==='events' && <><label htmlFor="event-branch">{copy.branch}<select id="event-branch" value={branch} onChange={event=>setBranch(event.target.value)}><option value="">{copy.allBranches}</option>{data?.branches.map(row=><option key={row.id} value={row.id}>{localized(row,'name',language)}</option>)}</select></label><label htmlFor="event-period">{copy.eventPeriod}<select id="event-period" value={period} onChange={event=>setPeriod(event.target.value)}><option value="upcoming">{copy.upcoming}</option><option value="past">{copy.past}</option></select></label></>}
   </div>}
   {!data ? <CatalogueState language={language} error={error} retry={retry}/> : <>
    {empty && <div className="catalogue-state" role="status"><h3>{copy.noMatches}</h3><p>{copy.noMatchesBody}</p>{page!=='programs' && <button type="button" className="home-text-link" onClick={reset}>{copy.reset}</button>}</div>}
    {page==='branches' && <div className="branch-directory">{branches.map(row=><article className="branch-entry" key={row.id} id={row.slug}>
     <div className="branch-summary"><h3>{localized(row,'name',language)}</h3><p>{localized(row,'description',language)}</p><a className="home-text-link" href={`/get-involved?branch=${row.id}`}>{copy.volunteer}<span aria-hidden="true"> ↗</span></a></div>
     <div className="branch-facts"><dl><div><dt>{copy.location}</dt><dd>{localized(row,'address',language)}</dd></div><div><dt>{copy.hours}</dt><dd>{localized(row,'hours',language)}</dd></div></dl><a className="home-text-link" href={`/contact?branch=${row.id}`}>{copy.askBranch}<span aria-hidden="true"> ↗</span></a>{row.is_demo && <p className="record-note">{copy.demo}</p>}</div>
    </article>)}</div>}
    {page==='events' && <div className="event-list">{events.map(row=>{const office=data.branches.find(item=>item.id===row.branch_id);return <article className="event-entry" key={row.id} id={row.slug}>
     <div className="event-date"><time dateTime={row.starts_at}>{eventDate(row.starts_at,language)}</time><span>{eventDate(row.starts_at,language,true)} – {eventDate(row.ends_at,language,true)}</span><span>{copy.pakistanTime}</span></div>
     <div className="event-copy"><h3>{localized(row,'title',language)}</h3><p className="event-location">{office && localized(office,'name',language)}</p><p>{localized(row,'description',language)}</p><a className="home-text-link" href={`/contact?branch=${row.branch_id}&subject=${encodeURIComponent(localized(row,'title',language))}`}>{copy.askEvent}<span aria-hidden="true"> ↗</span></a></div>
     {row.is_demo && <p className="record-note">{copy.demo}</p>}
    </article>;})}</div>}
    {page==='programs' && <div className="program-directory">{data.programs.map(row=><article className="program-entry" key={row.id} id={row.slug}><div><h3>{localized(row,'title',language)}</h3>{row.is_demo && <p className="record-note">{copy.demo}</p>}</div><div><p>{localized(row,'description',language)}</p><dl><dt>{copy.audience}</dt><dd>{localized(row,'audience',language)}</dd></dl><a className="home-text-link" href="/get-involved">{copy.programAction}<span aria-hidden="true"> ↗</span></a></div></article>)}</div>}
   </>}
  </section>
  <section className="directory-closing home-section"><h2>{page==='branches'?copy.visit:copy.takePart}</h2><div><p>{page==='branches'?copy.contactAsideBody:copy.takePartBody}</p><a className="home-button" href={page==='branches'?'/contact':'/get-involved'}>{page==='branches'?content[language].contact.title:content[language].hero.action}<span aria-hidden="true">↗</span></a></div></section>
 </>;
}
