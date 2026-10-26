import {useState} from 'react';
import {Feedback,Submit} from '../components/Feedback';
import {pktToday} from './display';
import type {CollectionFields} from './types';

interface Props {
  initial?:CollectionFields;
  collector:string;
  busy:boolean;
  locked?:boolean;
  onSubmit:(fields:CollectionFields,reason:string)=>Promise<void>;
  onCancel:()=>void;
}

export default function CollectionForm({initial,collector,busy,locked=false,onSubmit,onCancel}:Props) {
  const [draft,setDraft]=useState<CollectionFields>(()=>({amount:initial?.amount??'',collected_on:initial?.collected_on??pktToday(),collector_name:initial?.collector_name??collector,notes:initial?.notes??''}));
  const [reason,setReason]=useState('');
  const [error,setError]=useState('');
  const change=(key:keyof CollectionFields,value:string)=>setDraft(previous=>({...previous,[key]:value}));
  return <form className="collection-form" aria-busy={busy} onSubmit={event=>{
    event.preventDefault();
    if(busy||locked)return;
    const amount=draft.amount.trim();
    if(!/^(?:0|[1-9][0-9]{0,9})(?:\.[0-9]{1,2})?$/.test(amount)||/^0(?:\.0{1,2})?$/.test(amount)){
      setError('Enter a positive PKR amount with at most two decimal places.');return;
    }
    if(!draft.collector_name.trim()||draft.collected_on>pktToday()||(initial&&reason.trim().length<3)){
      setError('Check the collection date, collector and reason.');return;
    }
    setError('');void onSubmit({...draft,amount},reason);
  }}>
    <Feedback error={error}/>
    {locked&&<p role="status" className="hr-blocked">The editing window has ended. Your draft is shown below, but this entry can no longer be changed.</p>}
    <fieldset disabled={busy||locked}><legend className="sr-only">Collection details</legend>
      <div className="hr-edit-grid">
        <div><label htmlFor="collection-amount">Amount (PKR)</label><input id="collection-amount" inputMode="decimal" type="text" required maxLength={13} placeholder="0.00" value={draft.amount} onChange={event=>change('amount',event.target.value)}/></div>
        <div><label htmlFor="collection-date">Collection date</label><input id="collection-date" type="date" required max={pktToday()} value={draft.collected_on} onChange={event=>change('collected_on',event.target.value)}/><p className="hr-help">The date the money was collected (PKT).</p></div>
        <div className="collection-wide"><label htmlFor="collection-collector">Collected by</label><input id="collection-collector" required maxLength={120} dir="auto" value={draft.collector_name} onChange={event=>change('collector_name',event.target.value)}/></div>
      </div>
      <label htmlFor="collection-notes">Notes (optional)</label><textarea id="collection-notes" rows={3} maxLength={1000} dir="auto" value={draft.notes} onChange={event=>change('notes',event.target.value)}/><p className="hr-help">Use operational notes. Leave out donor contact details or financial account credentials.</p>
      {initial&&<><label htmlFor="collection-reason">Reason for change</label><textarea id="collection-reason" rows={3} required minLength={3} maxLength={500} value={reason} onChange={event=>setReason(event.target.value)}/></>}
      <Submit busy={busy} disabled={locked} idle={initial?'Save collection':'Record collection'} pending={initial?'Saving collection…':'Recording…'}/>
    </fieldset>
    <button type="button" className="secondary" disabled={busy} onClick={onCancel}>Cancel</button>
  </form>;
}
