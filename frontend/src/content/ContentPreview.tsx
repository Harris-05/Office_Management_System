import type {ContentPayload} from './types';

export default function ContentPreview({content}:{content:ContentPayload}) {
 return <div className="cms-preview-languages">{(['en','ur'] as const).map(language=>
  <article key={language} lang={language} dir={language==='ur'?'rtl':'ltr'}>
   <span className="cms-language">{language==='ur'?'اردو':'English'}</span>
   <h3>{language==='ur'?content.title_ur:content.title}</h3>
   <p className="cms-plain-text">{language==='ur'?content.description_ur:content.description}</p>
   {content.kind==='program'&&<p><strong>{language==='ur'?'شرکاء: ':'Audience: '}</strong>{language==='ur'?content.audience_ur:content.audience}</p>}
   {content.kind==='event'&&<p>{new Intl.DateTimeFormat(language==='ur'?'ur-PK':'en-GB',{dateStyle:'medium',timeStyle:'short',timeZone:'Asia/Karachi'}).format(new Date(content.starts_at))} – {new Intl.DateTimeFormat(language==='ur'?'ur-PK':'en-GB',{timeStyle:'short',timeZone:'Asia/Karachi'}).format(new Date(content.ends_at))} (PKT)</p>}
  </article>)}</div>;
}
