export interface Person { id: string; name: string }
export interface BranchOption extends Person { code: string; status: string }
export interface MemberSummary extends Person { code: string }
export interface Application extends Person {
  email: string; subject: string; message: string; branch: BranchOption | null;
  status: 'Pending' | 'Accepted' | 'Declined'; version: number;
  created_at: string; expires_at: string; reviewed_at: string | null;
  reviewer: Person | null; reason: string | null; member: MemberSummary | null;
}
export interface Member extends MemberSummary {
  email: string; branch: BranchOption; source_id: string | null;
  status: 'Active' | 'Inactive'; team: string; organisational_role: string;
  version: number; created_at: string; updated_at: string;
}
export interface Page<T> { items: T[]; total: number; offset: number; limit: number }
export interface HistoryEvent {
  id: string; actor: Person | null; action: string; reason: string | null;
  before: Record<string, unknown> | null; after: Record<string, unknown>; created_at: string;
}
