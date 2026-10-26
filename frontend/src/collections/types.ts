import type {BranchOption,Person,HistoryEvent,Page} from '../membership/types';
export type {BranchOption,Person,HistoryEvent,Page};
export interface CollectionFields {
  amount:string;
  collected_on:string;
  collector_name:string;
  notes:string;
}
export interface Collection extends CollectionFields {
  id:string; code:string; branch:BranchOption; currency:'PKR'; creator:Person|null;
  version:number; created_at:string; updated_at:string; locks_at:string;
  server_time:string; is_locked:boolean; can_edit:boolean;
}
export interface CollectionPage extends Page<Collection> {
  total_amount:string; currency:'PKR'; server_time:string;
}
