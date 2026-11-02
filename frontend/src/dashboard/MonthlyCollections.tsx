import {formatMoney} from '../collections/display';
import type {MonthlyTotal} from './types';

function monthLabel(month: string) {
  return new Intl.DateTimeFormat('en-GB', {month: 'short', year: 'numeric', timeZone: 'UTC'}).format(new Date(`${month}-01T00:00:00Z`));
}

export default function MonthlyCollections({rows}: {rows: MonthlyTotal[]}) {
  // Numbers are used only for chart geometry; all displayed amounts retain exact decimal strings.
  const maximum = Math.max(1, ...rows.map(row => Number(row.amount)));
  return <section className="dashboard-panel dashboard-monthly" aria-labelledby="monthly-title">
    <h2 id="monthly-title">Monthly collections</h2>
    <p>By actual collection date. Only months with recorded collections are shown.</p>
    {rows.length ? <>
      <div className="dashboard-bars" role="img" aria-label="Monthly collections bar chart. Exact figures appear in the table below.">
        {rows.map(row => <div className="dashboard-bar-row" key={row.month}><span>{monthLabel(row.month)}</span><svg viewBox="0 0 100 12" preserveAspectRatio="none" aria-hidden="true"><rect x="0" y="2" width={Math.max(0.25, Number(row.amount) / maximum * 100)} height="8"/></svg><span>{formatMoney(row.amount)}</span></div>)}
      </div>
      <details><summary>View monthly figures</summary><div className="dashboard-table-scroll"><table aria-label="Monthly collection figures"><thead><tr><th scope="col">Month</th><th scope="col" className="dashboard-number">Collections</th><th scope="col" className="dashboard-number">Amount (PKR)</th></tr></thead><tbody>{rows.map(row => <tr key={row.month}><th scope="row">{monthLabel(row.month)}</th><td className="dashboard-number">{row.count}</td><td className="dashboard-number">{formatMoney(row.amount)}</td></tr>)}</tbody></table></div></details>
    </> : <p className="dashboard-empty">No collections match this date range.</p>}
  </section>;
}
