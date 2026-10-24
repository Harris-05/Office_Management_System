import { useEffect, useRef, useState } from 'react';
import { ApiError, api, restore } from './api';
import type { User } from './types';
import LoginForm from './components/LoginForm';
import ChangePasswordForm from './components/ChangePasswordForm';
import StaffAccounts from './components/StaffAccounts';
import { Feedback } from './components/Feedback';
import './staff.css';
import BranchManagement from './branches/BranchManagement';

type StaffPage = 'home' | 'staff' | 'password' | 'branches';
const pageFromPath = (): StaffPage => window.location.pathname.replace(/\/$/,'') === '/staff/branches' ? 'branches' : 'home';

export default function App({ initialPage = 'home' }: { initialPage?: 'home' | 'branches' }) {
  const [user, setUser] = useState<User | null>(null);
  const [starting, setStarting] = useState(true);
  const [startupError, setStartupError] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [page, setPage] = useState<StaffPage>(initialPage);
  const running = useRef(false);
  const authGeneration = useRef(0);
  const renderGeneration = authGeneration.current;
  const navigate = (next: StaffPage, replace = false) => {
    const path = next === 'branches' ? '/staff/branches' : '/staff';
    if (window.location.pathname !== path) window.history[replace?'replaceState':'pushState'](null,'',path);
    setPage(next);
  };
  useEffect(() => { const back = () => setPage(pageFromPath()); window.addEventListener('popstate',back); return () => window.removeEventListener('popstate',back); }, []);
  async function start() {
    const generation = ++authGeneration.current;
    setStartupError(''); setStarting(true);
    try { const restored = await restore(); if (generation === authGeneration.current) setUser(restored); }
    catch (cause) { if (generation === authGeneration.current) setStartupError(cause instanceof Error ? cause.message : 'Service unavailable.'); }
    finally { if (generation === authGeneration.current) setStarting(false); }
  }
  useEffect(() => { void start(); return () => { authGeneration.current++; }; }, []);
  useEffect(() => {
    const expired = () => { authGeneration.current++; setStarting(false); setUser(null); setPage(pageFromPath()); setError(''); setNotice(''); };
    window.addEventListener('branch-session-invalid', expired);
    return () => window.removeEventListener('branch-session-invalid', expired);
  }, []);
  useEffect(() => { document.getElementById('screen-title')?.setAttribute('tabindex', '-1'); document.getElementById('screen-title')?.focus(); }, [starting, user, page]);
  async function signOut() {
    if (running.current) return;
    authGeneration.current++;
    running.current = true; setBusy(true); setError('');
    try { await api('/api/logout', 'POST'); setUser(null); navigate('home',true); setNotice(''); }
    catch (cause) {
      if (cause instanceof ApiError && cause.status === 401) { setUser(null); setPage('home'); }
      else setError(cause instanceof Error ? cause.message : 'Unable to sign out. Please try again.');
    } finally { running.current = false; setBusy(false); }
  }
  return <main className={`staff-shell layout${user ? ' signed-in' : ' staff-login'}${user && !user.must_change_password && page === 'branches' ? ' branch-workspace' : ''}`}>
    <aside className="intro">
      <a className="brand" href="/" aria-label="Branch Office home"><span className="brand-mark" aria-hidden="true">B</span> Branch Office</a>
      {user && !user.must_change_password && <nav className="staff-navigation" aria-label="Staff navigation"><button aria-current={page==='home'?'page':undefined} onClick={()=>navigate('home')}>Workspace</button>{['Super Admin','Branch Lead'].includes(user.role)&&<button aria-current={page==='branches'?'page':undefined} onClick={()=>navigate('branches')}>{user.role==='Super Admin'?'Branches':'My branch'}</button>}{user.role==='Super Admin'&&<button aria-current={page==='staff'?'page':undefined} onClick={()=>navigate('staff')}>Staff accounts</button>}</nav>}
      <div className="intro-copy"><p className="intro-heading">Every branch.<br />Shared purpose.</p><p>A shared workspace for the people keeping our branches and programmes moving.</p></div>
      <p className="intro-footer">People. Programmes. Progress.</p>
    </aside>
    <section className="workspace" aria-labelledby="screen-title">
      <div className="staff-topbar"><a href="/" className="staff-home-link"><span aria-hidden="true">← </span>Back to website</a><span className="top-note">Staff portal</span></div>
      <div className="card">
        {starting ? <><h1 id="screen-title">Opening your workspace</h1><p role="status">Checking your session…</p></> : startupError ? <><h1 id="screen-title">Unable to open workspace</h1><Feedback error={startupError} /><button className="primary" onClick={() => void start()}>Try again</button></> : !user ? <LoginForm onLogin={value => { if (renderGeneration !== authGeneration.current) return; setUser(value); setNotice('Signed in successfully.'); }} /> : <>
          <div className="account-toolbar"><span>{user.name} · {user.role}</span><button className="secondary" disabled={busy} onClick={() => void signOut()}>{busy ? 'Signing out…' : 'Sign out'}</button></div>
          <Feedback error={error} />
          {user.must_change_password || page === 'password' ? <><ChangePasswordForm required={user.must_change_password} onChanged={value => { if (renderGeneration !== authGeneration.current) return; setUser(value); setPage(page === 'branches'?'branches':'home'); setNotice('Password changed successfully.'); }} />{!user.must_change_password && <button className="secondary" onClick={() => navigate('home')}>Back to workspace</button>}</> : page === 'branches' ? <BranchManagement user={user}/> : page === 'staff' ? <><button className="secondary back" onClick={() => navigate('home')}>Back to workspace</button><StaffAccounts currentUser={user} /></> : <>
            <h1 id="screen-title">Your workspace</h1><Feedback success={notice} />
            <dl className="profile"><div><dt>Email</dt><dd>{user.email}</dd></div><div><dt>Role</dt><dd>{user.role}</dd></div></dl>
            {user.role === 'Super Admin' && <><button className="primary" onClick={() => navigate('branches')}>Manage branches</button><button className="secondary" onClick={() => navigate('staff')}>Manage staff accounts</button></>}
            {user.role === 'Branch Lead' && <button className="primary" onClick={()=>navigate('branches')}>My branch</button>}
            <button className="secondary" onClick={() => navigate('password')}>Change password</button>
          </>}
        </>}
      </div>
      <footer>Branch-to-Head-Office Management Platform</footer>
    </section>
  </main>;
}
