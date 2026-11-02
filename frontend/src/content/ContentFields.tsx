import type {BranchOption,ContentPayload,PageKey} from './types';

export default function ContentFields({value,onChange,branches,existing}:{value:ContentPayload;onChange:(value:ContentPayload)=>void;branches:BranchOption[];existing:boolean}) {
 const change=(key:string,next:string)=>onChange({...value,[key]:next});
 const field=(key:'title'|'title_ur'|'description'|'description_ur',label:string,textarea=false)=>
  <div><label htmlFor={`cms-${key}`}>{label}</label>{textarea?<textarea id={`cms-${key}`} value={value[key]} required maxLength={10000} rows={6} lang={key.endsWith('_ur')?'ur':'en'} dir={key.endsWith('_ur')?'rtl':'ltr'} onChange={event=>change(key,event.target.value)}/>:<input id={`cms-${key}`} value={value[key]} required maxLength={160} lang={key.endsWith('_ur')?'ur':'en'} dir={key.endsWith('_ur')?'rtl':'ltr'} onChange={event=>change(key,event.target.value)}/>}</div>;
 return <>
  <div className="cms-form-pair">{field('title','Title (English)')}{field('title_ur','Title (Urdu)')}</div>
  <div className="cms-form-pair">{field('description','Description (English)',true)}{field('description_ur','Description (Urdu)',true)}</div>
  <div className="cms-form-pair"><div><label htmlFor="cms-slug">Slug</label><input id="cms-slug" value={value.slug} required maxLength={100} pattern="[a-z0-9]+(-[a-z0-9]+)*" aria-describedby="cms-slug-help" onChange={event=>change('slug',event.target.value)}/><p id="cms-slug-help" className="cms-help">Lowercase letters, numbers and single hyphens.</p></div>
   {value.kind==='page'&&<div><label htmlFor="cms-page-key">Public page</label><select id="cms-page-key" value={value.page_key} disabled={existing} onChange={event=>onChange({...value,page_key:event.target.value as PageKey})}><option value="home">Home introduction</option><option value="about">About introduction</option><option value="contact">Contact introduction</option></select></div>}
  </div>
  {value.kind==='program'&&<div className="cms-form-pair"><div><label htmlFor="cms-audience">Audience (English)</label><input id="cms-audience" value={value.audience} maxLength={200} required onChange={event=>change('audience',event.target.value)}/></div><div><label htmlFor="cms-audience-ur">Audience (Urdu)</label><input id="cms-audience-ur" value={value.audience_ur} maxLength={200} required lang="ur" dir="rtl" onChange={event=>change('audience_ur',event.target.value)}/></div></div>}
  {value.kind==='event'&&<><div><label htmlFor="cms-event-branch">Event branch</label><select id="cms-event-branch" value={value.branch_id} required onChange={event=>change('branch_id',event.target.value)}><option value="">Choose an Active, published branch</option>{value.branch_id&&!branches.some(branch=>branch.id===value.branch_id)&&<option value={value.branch_id}>Current branch unavailable for publication</option>}{branches.map(branch=><option key={branch.id} value={branch.id}>{branch.name} · {branch.code}</option>)}</select><p className="cms-help">Branch management controls which offices may host public events.</p></div><div className="cms-form-pair"><div><label htmlFor="cms-start">Starts at (Pakistan time)</label><input id="cms-start" type="datetime-local" required value={localDate(value.starts_at)} onChange={event=>change('starts_at',toZoned(event.target.value))}/></div><div><label htmlFor="cms-end">Ends at (Pakistan time)</label><input id="cms-end" type="datetime-local" required value={localDate(value.ends_at)} onChange={event=>change('ends_at',toZoned(event.target.value))}/></div></div></>}
 </>;
}
function toZoned(value:string){return value?`${value}:00+05:00`:'';}
function localDate(value:string){
 if(!value)return '';
 const date=new Date(value);
 if(!Number.isFinite(date.getTime()))return '';
 return new Date(date.getTime()+5*60*60*1000).toISOString().slice(0,16);
}
