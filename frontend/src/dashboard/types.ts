import type {BranchOption, Page} from '../collections/types';

export type DashboardFilters = {branch_id: string; date_from: string; date_to: string};
export type MonthlyTotal = {month: string; count: number; amount: string};
export type DashboardData = {
  live_collections: {count: number; amount: string; currency: 'PKR'};
  monthly: MonthlyTotal[];
  reconciliation: {recorded: string; not_submitted: string; eligible: string; awaiting_confirmation: string; confirmed_received: string; currency: 'PKR'};
  outstanding: Page<{id: string; code: string; branch: BranchOption; amount: string; collected_on: string; locks_at: string; eligible: boolean}>;
  reports: {statuses: Record<string, number>; approved_collection_total: string; approved_transfer_total: string; approved_discrepancies: number};
  server_time: string;
};
