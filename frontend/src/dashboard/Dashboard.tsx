import {useRef, useState} from 'react';
import type {User} from '../types';
import useResource from '../branches/useResource';
import {BranchFilter, LoadState, Pagination, queryString} from '../membership/shared';
import {Feedback} from '../components/Feedback';
import {calendarDate, formatMoney} from '../collections/display';
import MonthlyCollections from './MonthlyCollections';
import {downloadCollections} from './download';
import type {DashboardData, DashboardFilters} from './types';
import '../membership/membership.css';
import './dashboard.css';

export default function Dashboard({user}: {user: User}) {
  if (!['Super Admin', 'Finance Reviewer', 'Branch Lead'].includes(user.role)) return <div className="membership"><h1 id="screen-title">Dashboard access unavailable</h1><p>The financial dashboard is available to Branch Leads, Finance Reviewers and Super Admins.</p></div>;
  return <FinancialDashboard user={user}/>;
}

function FinancialDashboard({user}: {user: User}) {
  const [filters, setFilters] = useState<DashboardFilters>({branch_id: '', date_from: '', date_to: ''});
  const [applied, setApplied] = useState(filters);
  const [branchLabel, setBranchLabel] = useState('');
  const [offset, setOffset] = useState(0);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState('');
  const [exportNotice, setExportNotice] = useState('');
  const running = useRef(false);
  const query = useResource<DashboardData>(`/api/dashboard?${queryString({...applied, offset, limit: 25})}`);
  const field = (key: keyof DashboardFilters, value: string) => setFilters(previous => ({...previous, [key]: value}));
  const download = async () => {
    if (running.current) return;
    running.current = true; setExporting(true); setExportError(''); setExportNotice('');
    try {await downloadCollections(queryString(applied)); setExportNotice('Collections CSV downloaded. It contains every collection matching the applied filters.');}
    catch (cause) {setExportError(cause instanceof Error ? cause.message : 'Unable to export collections. Please retry.');}
    finally {running.current = false; setExporting(false);}
  };
  return <div className="membership financial-dashboard" data-ui="dashboard">
    <header className="hr-heading"><div><h1 id="screen-title">Financial dashboard</h1><p>{user.role === 'Branch Lead' ? 'Your currently assigned branch. Read-only ledger and weekly report figures.' : 'Head office overview of branch collections and weekly reporting.'}</p></div><button type="button" className="secondary" disabled={exporting || !query.data || query.loading} onClick={download}>{exporting ? 'Exporting collections…' : 'Export collections CSV'}</button></header>
    <form className="hr-filters dashboard-filters" onSubmit={event => {event.preventDefault(); setOffset(0); setApplied({...filters}); setExportError(''); setExportNotice('');}}>
      {user.role !== 'Branch Lead' && <BranchFilter endpoint="/api/collections/branches" value={filters.branch_id} label={branchLabel} onChange={(value, label) => {field('branch_id', value); setBranchLabel(label);}}/>}
      <div><label htmlFor="dashboard-from">Collected from</label><input id="dashboard-from" type="date" value={filters.date_from} max={filters.date_to || undefined} onChange={event => field('date_from', event.target.value)}/></div>
      <div><label htmlFor="dashboard-to">Collected to</label><input id="dashboard-to" type="date" value={filters.date_to} min={filters.date_from || undefined} onChange={event => field('date_to', event.target.value)}/></div><button type="submit" className="secondary">Apply filters</button>
    </form>
    <Feedback error={exportError} success={exportNotice}/>
    <LoadState loading={query.loading} error={query.error} retry={query.reload}>{query.data && <>
      <div className="dashboard-live-total"><div><span>Live collection ledger</span><strong>{formatMoney(query.data.live_collections.amount)}</strong><p>{query.data.live_collections.count} collections across the applied date and branch filters.</p></div><button type="button" className="secondary" onClick={query.reload}>Refresh figures</button></div>
      <div className="dashboard-overview"><MonthlyCollections rows={query.data.monthly}/><ApprovedReports reports={query.data.reports}/></div>
      <Reconciliation balances={query.data.reconciliation}/>
      <Outstanding data={query.data.outstanding} offset={offset} setOffset={setOffset}/>
      <p className="dashboard-freshness">Figures retrieved <time dateTime={query.data.server_time}>{new Intl.DateTimeFormat('en-GB', {dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Karachi'}).format(new Date(query.data.server_time))} PKT</time>. Refresh to check later entries.</p>
    </>}</LoadState>
  </div>;
}

function ApprovedReports({reports}: {reports: DashboardData['reports']}) {
  return <section className="dashboard-panel" aria-labelledby="approved-title"><h2 id="approved-title">Weekly report snapshots</h2><p>Reports whose week starting date falls in the applied range. Approved figures stay frozen.</p><dl className="dashboard-report-statuses">{Object.entries(reports.statuses).map(([status, count]) => <div key={status}><dt>{status}</dt><dd>{count}</dd></div>)}</dl><dl className="dashboard-snapshot-totals"><div><dt>Approved collections</dt><dd>{formatMoney(reports.approved_collection_total)}</dd></div><div><dt>Approved transfers</dt><dd>{formatMoney(reports.approved_transfer_total)}</dd></div></dl>{reports.approved_discrepancies > 0 ? <p className="dashboard-discrepancy" role="status">{reports.approved_discrepancies} approved {reports.approved_discrepancies === 1 ? 'report differs' : 'reports differ'} from the current ledger. Approved figures are retained; review the report details.</p> : <p>No approved report discrepancies detected.</p>}</section>;
}

function Reconciliation({balances}: {balances: DashboardData['reconciliation']}) {
  const labels: [keyof Omit<typeof balances, 'currency'>, string][] = [['recorded', 'Recorded'], ['not_submitted', 'Not submitted'], ['eligible', 'Eligible for transfer'], ['awaiting_confirmation', 'Awaiting confirmation'], ['confirmed_received', 'Confirmed received']];
  return <section className="dashboard-panel" aria-labelledby="reconciliation-title"><h2 id="reconciliation-title">Cumulative transfer reconciliation</h2><p>All dates in the selected branch scope, independent of the collection date filter. Eligible is the locked portion of not submitted.</p><dl className="dashboard-reconciliation">{labels.map(([key, label]) => <div key={key}><dt>{label}</dt><dd>{formatMoney(balances[key])}</dd></div>)}</dl></section>;
}

function Outstanding({data, offset, setOffset}: {data: DashboardData['outstanding']; offset: number; setOffset: (value: number) => void}) {
  return <section className="dashboard-panel" aria-labelledby="outstanding-title"><h2 id="outstanding-title">Unallocated collections</h2><p>{data.total} collections across all dates in this branch scope. Open entries become eligible after their seven-day editing window; submission also requires an Active branch.</p>{data.items.length ? <div className="dashboard-table-scroll"><table aria-label="Unallocated collections"><thead><tr><th scope="col">Collection / branch</th><th scope="col">Collected</th><th scope="col">Editing window</th><th scope="col" className="dashboard-number">Amount (PKR)</th></tr></thead><tbody>{data.items.map(row => <tr key={row.id}><th scope="row"><span className="dashboard-code">{row.code}</span><span className="dashboard-branch">{row.branch.name} · {row.branch.code}</span></th><td>{calendarDate(row.collected_on)}</td><td>{row.eligible ? 'Eligible' : 'Open window'}{row.branch.status !== 'Active' && <span className="dashboard-branch">Branch {row.branch.status}</span>}</td><td className="dashboard-number">{formatMoney(row.amount)}</td></tr>)}</tbody></table></div> : <p className="dashboard-empty">No unallocated collections in this branch scope.</p>}<Pagination offset={offset} total={data.total} limit={data.limit} onChange={setOffset}/></section>;
}
