import type {BranchOption,Person,Page} from '../membership/types';
export type {BranchOption,Page};
export interface TransferMetadata {transferred_on:string;reference:string;notes:string}
export interface EligibleCollection {id:string;code:string;amount:string;collected_on:string;collector_name:string}
export interface Transfer extends TransferMetadata {
  id:string;code:string;branch:BranchOption;amount:string;currency:'PKR';
  status:'Submitted'|'Returned'|'Confirmed'|'Cancelled';version:number;
  creator:Person|null;reviewer:Person|null;created_at:string;updated_at:string;confirmed_at:string|null;
  items:{collection_id:string;code:string;amount:string;collected_on:string;collection_version:number}[];
  can_confirm:boolean;can_return:boolean;can_cancel:boolean;can_resubmit:boolean;
}
export interface Balances {
  recorded:string;not_submitted:string;eligible:string;awaiting_confirmation:string;confirmed_received:string;currency:'PKR';
}

export function selectedTotal(rows:{amount:string}[]):string {
  const cents=rows.reduce((sum,row)=>{
    const [whole,fraction='00']=row.amount.split('.');
    return sum+BigInt(whole)*100n+BigInt(fraction.padEnd(2,'0'));
  },0n);
  return `${cents/100n}.${String(cents%100n).padStart(2,'0')}`;
}
