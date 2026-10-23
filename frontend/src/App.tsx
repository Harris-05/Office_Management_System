import { useEffect, useRef, useState } from 'react';
import { ApiError, api, restore } from './api';
import type { User } from './types';
import LoginForm from './components/LoginForm';
import ChangePasswordForm from './components/ChangePasswordForm';
import StaffAccounts from './components/StaffAccounts';
import { Feedback } from './components/Feedback';

export default function App() {
  const [user, setUser] = useState<User | null>(null);
  const [starting, setStarting] = useState(true);
  const [startupError, setStartupError] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [page, setPage] = useState<'home' | 'staff' | 'password'>('home');
  const running = useRef(false);
  async function start() {
    setStartupError(''); setStarting(true);
    try { setUser(await restore()); }
    catch (cause) { setStartupError(cause instanceof Error ? cause.message : 'Service unavailable.'); }
    finally { setStarting(false); }
  }
  useEffect(() => { void start(); }, []);
  useEffect(() => {
    const expired = () => { setUser(null); setPage('home'); setError(''); setNotice(''); };
    window.addEventListener('branch-session-invalid', expired);
    return () => window.removeEventListener('branch-session-invalid', expired);
  }, []);
  useEffect(() => { document.getElementById('screen-title')?.setAttribute('tabindex', '-1'); document.getElementById('screen-title')?.focus(); }, [starting, user, page]);
  async function signOut() {
    if (running.current) return;
    running.current = true; setBusy(true); setError('');
    try { await api('/api/logout', 'POST'); setUser(null); setPage('home'); setNotice(''); }
    catch (cause) {
      if (cause instanceof ApiError && cause.status === 401) { setUser(null); setPage('home'); }
      else setError(cause instanceof Error ? cause.message : 'Unable to sign out. Please try again.');
    } finally { running.current = false; setBusy(false); }
  }
  return <main className={`layout${user ? ' signed-in' : ''}`}>
    <aside className="intro">
      <div className="brand"><span className="brand-mark" aria-hidden="true">B</span> Branch Office</div>
      <div className="intro-copy"><p className="intro-heading">Every branch.<br />Shared purpose.</p><p>A shared workspace for the people keeping our branches and programmes moving.</p></div>
      <p className="intro-footer">People. Programmes. Progress.</p>
    </aside>
    <section className="workspace" aria-labelledby="screen-title">
      <div className="top-note">Staff portal</div>
      <div className="card">
        {starting ? <><h1 id="screen-title">Opening your workspace</h1><p role="status">Checking your session…</p></> : startupError ? <><h1 id="screen-title">Unable to open workspace</h1><Feedback error={startupError} /><button className="primary" onClick={() => void start()}>Try again</button></> : !user ? <LoginForm onLogin={value => { setUser(value); setNotice('Signed in successfully.'); }} /> : <>
          <div className="account-toolbar"><span>{user.name} · {user.role}</span><button className="secondary" disabled={busy} onClick={() => void signOut()}>{busy ? 'Signing out…' : 'Sign out'}</button></div>
          <Feedback error={error} />
          {user.must_change_password || page === 'password' ? <><ChangePasswordForm required={user.must_change_password} onChanged={value => { setUser(value); setPage('home'); setNotice('Password changed successfully.'); }} />{!user.must_change_password && <button className="secondary" onClick={() => setPage('home')}>Back to workspace</button>}</> : page === 'staff' ? <><button className="secondary back" onClick={() => setPage('home')}>Back to workspace</button><StaffAccounts currentUser={user} /></> : <>
            <h1 id="screen-title">Your workspace</h1><Feedback success={notice} />
            <dl className="profile"><div><dt>Email</dt><dd>{user.email}</dd></div><div><dt>Role</dt><dd>{user.role}</dd></div></dl>
            {user.role === 'Super Admin' && <button className="primary" onClick={() => setPage('staff')}>Manage staff accounts</button>}
            <button className="secondary" onClick={() => setPage('password')}>Change password</button>
          </>}
        </>}
      </div>
      <footer>Branch-to-Head-Office Management Platform</footer>
    </section>
  </main>;
}
