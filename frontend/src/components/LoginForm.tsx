import { useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { api } from '../api';
import type { User } from '../types';
import { Feedback, Submit } from './Feedback';

export default function LoginForm({ onLogin }: { onLogin: (user: User) => void }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [visible, setVisible] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const running = useRef(false);
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (running.current) return;
    running.current = true; setBusy(true); setError('');
    try { const user = await api<User>('/api/login', 'POST', { email, password }); setPassword(''); onLogin(user); }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Sign-in failed. Please try again.'); }
    finally { running.current = false; setBusy(false); }
  }
  return <>
    <h1 id="screen-title">Sign in to your workspace</h1>
    <p className="description">Use the credentials provided by your administrator.</p>
    <form onSubmit={submit} aria-busy={busy}>
      <Feedback error={error} />
      <label htmlFor="email">Email address</label>
      <input id="email" type="email" autoComplete="username" value={email} onChange={e => { setEmail(e.target.value); setError(''); }} required maxLength={254} disabled={busy} />
      <label htmlFor="password">Password</label>
      <div className="password-field">
        <input id="password" type={visible ? 'text' : 'password'} autoComplete="current-password" value={password} onChange={e => { setPassword(e.target.value); setError(''); }} required maxLength={128} disabled={busy} />
        <button type="button" className="show-password" disabled={busy} aria-pressed={visible} aria-label={visible ? 'Hide password' : 'Show password'} onClick={() => setVisible(!visible)}>{visible ? 'Hide' : 'Show'}</button>
      </div>
      <Submit busy={busy} idle="Sign in" pending="Signing in…" />
      <p className="request-status" role="status">{busy ? 'Checking your details. Please wait…' : ''}</p>
    </form>
    <p className="demo-note">Need an account or a password reset? Contact your Super Admin.</p>
  </>;
}
