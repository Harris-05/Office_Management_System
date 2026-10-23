import { useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { api } from '../api';
import type { User } from '../types';
import { Feedback, Submit, passwordError } from './Feedback';

export default function ChangePasswordForm({ onChanged, required }: { onChanged: (user: User) => void; required: boolean }) {
  const [current, setCurrent] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const running = useRef(false);
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (running.current) return;
    const invalid = passwordError(password) ?? (password !== confirm ? 'New passwords do not match.' : null);
    if (invalid) { setError(invalid); return; }
    running.current = true; setBusy(true); setError('');
    try {
      const result = await api<User>('/api/change-password', 'POST', { current_password: current, new_password: password, confirm_password: confirm });
      setCurrent(''); setPassword(''); setConfirm(''); onChanged(result);
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Password change failed.'); }
    finally { running.current = false; setBusy(false); }
  }
  return <>
    <h1 id="screen-title">{required ? 'Set your own password' : 'Change your password'}</h1>
    <p className="description">{required ? 'Replace your temporary password before accessing your workspace.' : 'Updating your password signs out your other sessions.'}</p>
    <form onSubmit={submit} aria-busy={busy}>
      <Feedback error={error} />
      <label htmlFor="current-password">Current password</label>
      <input id="current-password" type="password" autoComplete="current-password" value={current} onChange={e => setCurrent(e.target.value)} required maxLength={128} disabled={busy} />
      <label htmlFor="new-password">New password</label>
      <input id="new-password" type="password" autoComplete="new-password" value={password} onChange={e => setPassword(e.target.value)} required minLength={15} maxLength={72} disabled={busy} aria-describedby="password-help" />
      <p id="password-help" className="field-help">At least 15 characters, at most 72 UTF-8 bytes. Choose a different password.</p>
      <label htmlFor="confirm-password">Confirm new password</label>
      <input id="confirm-password" type="password" autoComplete="new-password" value={confirm} onChange={e => setConfirm(e.target.value)} required minLength={15} maxLength={72} disabled={busy} />
      <Submit busy={busy} idle="Save password" pending="Saving password…" />
    </form>
  </>;
}
