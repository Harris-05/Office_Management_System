import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { api } from '../api';
import type { User } from '../types';
import { Feedback, Submit, passwordError } from './Feedback';

const roles = ['Super Admin', 'Finance Reviewer', 'Content Editor', 'Branch Lead', 'HR Lead'];

export default function StaffAccounts({ currentUser }: { currentUser: User }) {
  const [rows, setRows] = useState<User[]>([]);
  const [offset, setOffset] = useState(0);
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [role, setRole] = useState('Branch Lead');
  const [password, setPassword] = useState('');
  const [resetUser, setResetUser] = useState<User | null>(null);
  const [resetPassword, setResetPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const running = useRef(false);
  async function load() {
    setLoading(true);
    try { setRows(await api<User[]>(`/api/staff?offset=${offset}&limit=25`)); }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to load staff.'); }
    finally { setLoading(false); }
  }
  useEffect(() => { void load(); }, [offset]);
  async function submit(event: FormEvent, reset = false) {
    event.preventDefault();
    if (running.current) return;
    const invalid = passwordError(reset ? resetPassword : password);
    if (invalid) { setError(invalid); return; }
    running.current = true; setBusy(true); setError(''); setSuccess('');
    try {
      if (reset && resetUser) {
        await api(`/api/staff/${resetUser.id}/reset-password`, 'POST', { temporary_password: resetPassword });
        setResetPassword(''); setResetUser(null); setSuccess('Temporary password reset. Share it directly with the staff member.');
      } else {
        await api('/api/staff', 'POST', { name, email, role, temporary_password: password });
        setName(''); setEmail(''); setPassword(''); setSuccess('Account created. Share the credentials directly with the staff member.');
      }
      await load();
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to complete request.'); }
    finally { running.current = false; setBusy(false); }
  }
  return <>
    <h1 id="screen-title">Staff accounts</h1>
    <p className="description">Create staff logins and hand over credentials directly. Temporary passwords expire in 48 hours.</p>
    <Feedback error={error} success={success} />
    <div className="staff-columns">
      <section aria-labelledby="create-title">
        <h3 id="create-title">Create staff account</h3>
        <form onSubmit={event => submit(event)} aria-busy={busy}>
          <label htmlFor="staff-name">Full name</label>
          <input id="staff-name" value={name} onChange={e => setName(e.target.value)} required maxLength={120} disabled={busy} autoComplete="off" />
          <label htmlFor="staff-email">Staff email</label>
          <input id="staff-email" type="email" value={email} onChange={e => setEmail(e.target.value)} required maxLength={254} disabled={busy} autoComplete="off" />
          <label htmlFor="staff-role">System role</label>
          <select id="staff-role" value={role} onChange={e => setRole(e.target.value)} disabled={busy}>{roles.map(item => <option key={item}>{item}</option>)}</select>
          <label htmlFor="temporary-password">Temporary password</label>
          <input id="temporary-password" type="password" value={password} onChange={e => setPassword(e.target.value)} required minLength={15} maxLength={72} disabled={busy} autoComplete="new-password" aria-describedby="temporary-help" />
          <p id="temporary-help" className="field-help">15+ characters, max 72 UTF-8 bytes. The user must change it at first login. Record it before submitting; it cannot be retrieved afterward.</p>
          <Submit busy={busy} idle="Create account" pending="Saving…" />
        </form>
      </section>
      <section aria-labelledby="staff-list-title">
        <h3 id="staff-list-title">Existing staff</h3>
        {loading ? <p className="description">Loading staff…</p> : rows.length === 0 ? <p>No staff accounts on this page.</p> : <ul className="staff-list">{rows.map(row => <li key={row.id}>
          <div><strong>{row.name}</strong><span>{row.email}</span><small>{row.role}{row.must_change_password ? ' · Password change required' : ''}</small></div>
          {row.id !== currentUser.id && <button type="button" className="secondary" disabled={busy} onClick={() => { setResetUser(row); setResetPassword(''); setError(''); setSuccess(''); }}>Reset password<span className="sr-only"> for {row.email}</span></button>}
        </li>)}</ul>}
        <div className="pagination"><button className="secondary" disabled={busy || loading || offset === 0} onClick={() => setOffset(Math.max(0, offset - 25))}>Previous</button><button className="secondary" disabled={busy || loading || rows.length < 25} onClick={() => setOffset(offset + 25)}>Next</button></div>
        {resetUser && <form onSubmit={event => submit(event, true)} className="reset-form">
          <h3>Reset {resetUser.name}'s password</h3>
          <p className="field-help">Existing sessions will be signed out. Hand over the new temporary password directly.</p>
          <label htmlFor="reset-password">New temporary password</label>
          <input id="reset-password" type="password" value={resetPassword} onChange={e => setResetPassword(e.target.value)} required minLength={15} maxLength={72} disabled={busy} autoComplete="new-password" />
          <Submit busy={busy} idle="Reset temporary password" pending="Resetting…" />
          <button className="secondary" type="button" disabled={busy} onClick={() => { setResetUser(null); setResetPassword(''); }}>Cancel reset</button>
        </form>}
      </section>
    </div>
  </>;
}
