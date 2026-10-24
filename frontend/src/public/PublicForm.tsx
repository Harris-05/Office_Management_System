import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { api, ApiError } from '../api';
import type { Branch } from './catalogue';
import { localized } from './catalogue';
import type { Language } from './content';
import { publicCopy } from './publicCopy';

type FieldName='name'|'email'|'subject'|'message'|'branch_id'|'consent';
export default function PublicForm({kind,language,branches}:{kind:'contact'|'volunteer';language:Language;branches:Branch[]}) {
 const copy=publicCopy[language];
 const form=useRef<HTMLFormElement>(null);
 const success=useRef<HTMLDivElement>(null);
 const busy=useRef(false);
 const request=useRef({body:'',id:''});
 const [pending,setPending]=useState(false);
 const [receipt,setReceipt]=useState('');
 const [errors,setErrors]=useState<Partial<Record<FieldName,string>>>({});
 const [failure,setFailure]=useState('');
 const [cooldown,setCooldown]=useState(0);
 const params=new URLSearchParams(window.location.search);
 const initialBranch=params.get('branch') ?? '';
 useEffect(()=>{if(receipt)success.current?.focus();},[receipt]);
 useEffect(()=>{if(!cooldown)return; const timer=setTimeout(()=>setCooldown(value=>Math.max(0,value-1)),1000);return()=>clearTimeout(timer);},[cooldown]);
 const submit=async(event:FormEvent<HTMLFormElement>)=>{
  event.preventDefault();
  if(busy.current||cooldown)return;
  const fields=new FormData(event.currentTarget);
  const value=(name:FieldName)=>String(fields.get(name)??'').trim();
  const body={name:value('name'),email:value('email'),subject:kind==='volunteer'?'Volunteer interest':value('subject'),message:value('message'),branch_id:value('branch_id')||null,consent:fields.has('consent')};
  const next:Partial<Record<FieldName,string>>={};
  if(body.name.length<2||body.name.length>120)next.name='nameError';
  if(!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(body.email)||body.email.length>254)next.email='emailError';
  if(body.subject.length<2||body.subject.length>160)next.subject='subjectError';
  if(body.message.length<10||body.message.length>4000)next.message='messageError';
  if((kind==='volunteer'&&!body.branch_id)||(body.branch_id&&!branches.some(row=>row.id===body.branch_id)))next.branch_id='branchError';
  if(!body.consent)next.consent='consentError';
  setErrors(next);setFailure('');
  const first=Object.keys(next)[0];
  if(first){(form.current?.elements.namedItem(first) as HTMLElement)?.focus();return;}
  const serialized=JSON.stringify(body);
  if(request.current.body!==serialized)request.current={body:serialized,id:crypto.randomUUID()};
  busy.current=true;setPending(true);
  try {
   const result=await api<{id:string}>(`/api/public/${kind==='contact'?'messages':'volunteers'}`,'POST',{...body,request_id:request.current.id});
   setReceipt(result.id);
  }catch(error){
   if(error instanceof ApiError && error.status===429){setFailure('rateLimit');setCooldown(error.retryAfter??60);}
   else setFailure(error instanceof ApiError && error.status===403?'expired':error instanceof ApiError && error.status===409?'conflict':'failed');
  }finally{busy.current=false;setPending(false);}
 };
 const errorText=(key:string)=>copy[key as keyof typeof copy] as string;
 const input=(name:FieldName,label:string,type='text',maxLength=120)=><div className="public-field"><label htmlFor={`public-${name}`}>{label}</label><input id={`public-${name}`} name={name} type={type} maxLength={maxLength} autoComplete={name==='name'?'name':name==='email'?'email':undefined} dir={name==='email'?'ltr':undefined} required aria-invalid={Boolean(errors[name])} aria-describedby={errors[name]?`error-${name}`:undefined} defaultValue={name==='subject'?(params.get('subject')??'').slice(0,160):undefined}/>{errors[name] && <span className="field-error" id={`error-${name}`}>{errorText(errors[name])}</span>}</div>;
 if(receipt)return <div ref={success} className="public-form-success" role="status" tabIndex={-1}><h2>{kind==='contact'?copy.success:copy.volunteerSuccess}</h2><p>{kind==='contact'?copy.successBody:copy.volunteerSuccessBody}</p><p>{copy.receipt}<strong className="submission-reference" dir="ltr">{receipt}</strong></p><a href="/events" className="home-text-link">{copy.allEvents}<span aria-hidden="true"> ↗</span></a><button type="button" className="home-button" onClick={()=>{setReceipt('');request.current={body:'',id:''};}}>{copy.another}</button></div>;
 return <form ref={form} className="public-form" onSubmit={submit} noValidate aria-busy={pending}>
  <p className="form-note">{copy.required}</p>
  {Object.keys(errors).length>0 && <p className="form-error" role="alert">{copy.invalid}</p>}
  {failure && <p className="form-error" role="alert">{errorText(failure)}{cooldown>0 && ` (${cooldown} ${copy.seconds})`}</p>}
  <fieldset disabled={pending}><legend className="sr-only">{kind==='contact'?copy.contactHeading:copy.joinHeading}</legend>
   <div className="public-form-row">{input('name',copy.name)}{input('email',copy.email,'email',254)}</div>
   {kind==='contact' && input('subject',copy.subject,'text',160)}
   {(kind==='volunteer'||branches.length>0) && <div className="public-field"><label htmlFor="public-branch_id">{kind==='volunteer'?copy.branch:copy.optionalBranch}</label><select id="public-branch_id" name="branch_id" defaultValue={branches.some(row=>row.id===initialBranch)?initialBranch:''} required={kind==='volunteer'} aria-invalid={Boolean(errors.branch_id)} aria-describedby={errors.branch_id?'error-branch':undefined}><option value="">{kind==='volunteer'?copy.chooseBranch:copy.general}</option>{branches.map(row=><option key={row.id} value={row.id}>{localized(row,'name',language)}</option>)}</select>{errors.branch_id && <span id="error-branch" className="field-error">{copy.branchError}</span>}</div>}
   <div className="public-field"><label htmlFor="public-message">{kind==='contact'?copy.message:copy.interest}</label><textarea id="public-message" name="message" rows={6} minLength={10} maxLength={4000} required aria-invalid={Boolean(errors.message)} aria-describedby={errors.message?'error-message':undefined}/>{errors.message && <span id="error-message" className="field-error">{copy.messageError}</span>}</div>
   <p id="submission-privacy" className="form-note">{copy.privacy}</p>
   <label className="public-consent"><input type="checkbox" name="consent" required aria-invalid={Boolean(errors.consent)} aria-describedby={`submission-privacy${errors.consent?' error-consent':''}`}/><span>{copy.consent}</span></label>
   {errors.consent && <p id="error-consent" className="field-error">{copy.consentError}</p>}
  </fieldset>
  <div className="form-submit"><button className="home-button" type="submit" disabled={pending||cooldown>0}>{pending && <span className="public-spinner" aria-hidden="true"/>}{pending?copy.sending:kind==='contact'?copy.send:copy.sendVolunteer}</button><p className="form-note">{copy.noEmail}</p></div>
 </form>;
}
