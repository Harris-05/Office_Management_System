import type { Language } from './content';
import { eventDate, localized, useCatalogue } from './catalogue';
import { publicCopy } from './publicCopy';
import CatalogueState from './CatalogueState';

export default function HomeEvents({language}:{language:Language}) {
 const {data,error,retry}=useCatalogue();
 const copy=publicCopy[language];
 const events=data?.events.filter(row=>Date.parse(row.ends_at)>=Date.now()).sort((a,b)=>Date.parse(a.starts_at)-Date.parse(b.starts_at)).slice(0,2)??[];
 return <section className="home-events home-section" aria-labelledby="home-events-title"><div className="directory-heading"><h2 id="home-events-title" data-home-reveal>{copy.latest}</h2><div data-home-reveal><p>{copy.latestBody}</p><a className="home-text-link" href="/events">{copy.allEvents}<span aria-hidden="true"> ↗</span></a></div></div>
  {!data?<CatalogueState language={language} error={error} retry={retry}/>:events.length?<div className="home-event-list">{events.map(row=><article key={row.id}><time dateTime={row.starts_at}>{eventDate(row.starts_at,language)}</time><h3><a href={`/events#${row.slug}`}>{localized(row,'title',language)}<span aria-hidden="true"> ↗</span></a></h3><p>{localized(row,'description',language)}</p>{row.is_demo&&<p className="record-note">{copy.demo}</p>}</article>)}</div>:<p className="catalogue-state">{copy.noMatchesBody}</p>}
 </section>;
}
