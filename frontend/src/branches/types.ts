export const statuses = ['Forming', 'Active', 'Paused', 'Closed'] as const;
export type BranchStatus = typeof statuses[number];
export const transitions: Record<BranchStatus, BranchStatus[]> = {Forming:['Active','Closed'],Active:['Paused','Closed'],Paused:['Active','Closed'],Closed:[]};
export const fieldDefinitions = [
 ['name','Branch name',160],['city','City',100],['address','Address',300],
 ['hours','Office hours',160],['description','Description',4000],
] as const;
export type BranchFields = Record<'name'|'name_ur'|'city'|'city_ur'|'address'|'address_ur'|'hours'|'hours_ur'|'description'|'description_ur',string>;
export interface Branch extends BranchFields {
 id:string;code:string;slug:string;status:BranchStatus;is_published:boolean;is_demo:boolean;version:number;
 lead:{id:string;name:string}|null;created_at:string;updated_at:string;
}
export interface Page<T> {items:T[];total:number;offset:number;limit:number}
export interface Lead {id:string;name:string;email:string;branch_id:string|null;branch_code:string|null}
export interface Audit {id:string;actor:{id:string;name:string}|null;action:string;reason:string|null;before:Record<string,unknown>|null;after:Record<string,unknown>;created_at:string}
