import { content } from './content';
import type { Language } from './content';
import { publicCopy } from './publicCopy';
import { useCatalogue } from './catalogue';
import PublicForm from './PublicForm';
import CatalogueState from './CatalogueState';

export default function ContactPage({language,join=false}:{language:Language;join?:boolean}) {
 const copy=publicCopy[language];
 const base=content[language];
 const {data,error,retry}=useCatalogue();
 return <>
  <section className="public-intro home-section"><h1 data-home-reveal>{join?base.join.title:base.contact.title}</h1><p data-home-reveal>{join?copy.joinIntro:copy.contactIntro}</p></section>
  <section className="contact-layout home-section" aria-labelledby="contact-heading">
   <div className="contact-explanation"><h2 id="contact-heading" data-home-reveal>{join?copy.joinHeading:copy.contactHeading}</h2><p data-home-reveal>{join?copy.joinBody:copy.contactBody}</p>
    {join?<ol className="join-steps">{base.join.steps.map(step=><li key={step.title} data-home-reveal><h3>{step.title}</h3><p>{step.body}</p></li>)}</ol>:<div className="contact-aside"><h3 data-home-reveal>{copy.contactAside}</h3><p data-home-reveal>{copy.contactAsideBody}</p><a href="/branches" className="home-text-link" data-home-reveal>{copy.branches}<span aria-hidden="true"> ↗</span></a></div>}
    {join && data?.branches.some(row=>row.is_demo) && <p className="demo-notice">{copy.joinNotice}</p>}
   </div>
   <div className="contact-form-surface">{!data?<CatalogueState language={language} error={error} retry={retry}/>:join&&!data.branches.length?<div className="catalogue-state"><p>{copy.noMatchesBody}</p><a className="home-text-link" href="/contact">{base.contact.title}</a></div>:<PublicForm language={language} kind={join?'volunteer':'contact'} branches={data.branches}/>}</div>
  </section>
  <section className="public-faq home-section"><h2 data-home-reveal>{copy.faq}</h2><div>{copy.faqs.map(item=><details key={item.q} data-home-reveal><summary>{item.q}</summary><p>{item.a}</p></details>)}</div></section>
 </>;
}
