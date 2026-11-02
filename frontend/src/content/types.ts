export type ContentKind = 'program' | 'event' | 'page';
export type PageKey = 'home' | 'about' | 'contact';
interface TextContent {slug:string;title:string;title_ur:string;description:string;description_ur:string}
export type ProgramContent = TextContent & {kind:'program';audience:string;audience_ur:string};
export type EventContent = TextContent & {kind:'event';branch_id:string;starts_at:string;ends_at:string};
export type PageContent = TextContent & {kind:'page';page_key:PageKey};
export type ContentPayload = ProgramContent | EventContent | PageContent;
export interface ContentDocument {
 id:string;kind:ContentKind;version:number;draft:ContentPayload;published:ContentPayload|null;
 is_published:boolean;has_unpublished_changes:boolean;is_demo:boolean;updated_at:string;
}
export interface Page<T> {items:T[];total:number;offset:number;limit:number}
export interface BranchOption {id:string;name:string;name_ur:string;code:string}
export interface Revision {id:string;version:number;action:string;reason:string;actor:{id:string;name:string}|null;created_at:string;snapshot:{draft:ContentPayload;published:ContentPayload|null;is_published:boolean}}

export function blankContent(kind:ContentKind):ContentPayload {
 const common={slug:'',title:'',title_ur:'',description:'',description_ur:''};
 if(kind==='program')return {...common,kind,audience:'',audience_ur:''};
 if(kind==='event')return {...common,kind,branch_id:'',starts_at:'',ends_at:''};
 return {...common,kind,page_key:'home'};
}
