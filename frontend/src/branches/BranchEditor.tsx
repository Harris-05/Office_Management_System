import {useState} from 'react';
import type {FormEvent} from 'react';
import {Feedback,Submit} from '../components/Feedback';
import {fieldDefinitions} from './types';
import type {BranchFields} from './types';

export default function BranchEditor({initial,busy,onSubmit,onCancel}:{initial?:BranchFields;busy:boolean;onSubmit:(values:BranchFields)=>Promise<void>;onCancel:()=>void}) {
 const [draft,setDraft]=useState<BranchFields>(()=>Object.fromEntries(fieldDefinitions.flatMap(([key])=>[[key,initial?.[key]??''],[`${key}_ur`,initial?.[`${key}_ur` as keyof BranchFields]??'']])) as BranchFields);
 const [error,setError]=useState('');
 const submit=(event:FormEvent<HTMLFormElement>)=>{
  event.preventDefault();if(busy)return;
  const blank=Object.keys(draft).find(key=>!draft[key as keyof BranchFields].trim());
  if(blank){setError('Complete every English and Urdu field.');(event.currentTarget.elements.namedItem(blank) as HTMLElement)?.focus();return;}
  setError('');void onSubmit(draft);
 };
 return <form className="branch-editor" onSubmit={submit} aria-busy={busy}>
  <p className="branch-help">{initial?'Update the branch profile. Its code and public link stay the same.':'A branch code is generated when you save. New branches start as Forming and unpublished.'}</p>
  <Feedback error={error}/>
  <fieldset disabled={busy}><legend className="sr-only">Branch details</legend><div className="branch-language-columns">{(['en','ur'] as const).map(language=><section key={language} className="branch-language"><h2>{language==='en'?'English details':'Urdu details'}</h2>{fieldDefinitions.map(([key,label,max])=>{
   const field=(language==='en'?key:`${key}_ur`) as keyof BranchFields;
   const props={id:`branch-${field}`,name:field,value:draft[field],maxLength:max,required:true,dir:language==='ur'?'rtl' as const:'ltr' as const,lang:language,onChange:(event:React.ChangeEvent<HTMLInputElement|HTMLTextAreaElement>)=>setDraft(value=>({...value,[field]:event.target.value}))};
   return <div className="branch-field" key={field}><label htmlFor={props.id}>{label} ({language==='en'?'English':'Urdu'})</label>{key==='description'?<textarea {...props} rows={4}/>:<input {...props}/>}</div>;
  })}</section>)}</div></fieldset>
  <div className="branch-form-actions"><Submit busy={busy} idle={initial?'Save details':'Create branch'} pending="Saving branch…"/><button className="secondary" type="button" disabled={busy} onClick={onCancel}>Cancel</button></div>
 </form>;
}
