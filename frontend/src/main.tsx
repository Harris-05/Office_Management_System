import { StrictMode, useState } from 'react';
import type { FormEvent } from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';

type User = { name: string; email: string; role: string };

const accounts = [
  ['Super Admin', 'admin@example.test'],
  ['Finance Reviewer', 'finance@example.test'],
  ['Content Editor', 'editor@example.test'],
  ['Branch Lead', 'branch@example.test'],
  ['HR Lead', 'hr@example.test'],
];

function App() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [user, setUser] = useState<User | null>(null);

  async function signIn(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    setError('');
    setBusy(true);
    try {
      const response = await fetch('/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
        signal: AbortSignal.timeout(10000),
      });
      if (response.status === 401) {
        setError('Incorrect email or password. Please try again.');
        return;
      }
      if (!response.ok) throw new Error('Login unavailable');
      const profile: User = await response.json();
      setUser(profile);
      setPassword('');
    } catch {
      setError('Unable to connect. Check that the backend is running and try again.');
    } finally {
      setBusy(false);
    }
  }

  function signOut() {
    setUser(null);
    setPassword('');
    setError('');
  }

  return (
    <main className="layout">
      <aside className="intro">
        <div className="brand"><span className="brand-mark" aria-hidden="true">B</span> Branch Office</div>
        <div className="intro-copy">
          <p className="eyebrow">BRANCH TO HEAD OFFICE</p>
          <h1>One place.<br />Every branch.<br /><span>Shared purpose.</span></h1>
          <p>A shared workspace for the people keeping our branches and programmes moving.</p>
          <div className="connection" aria-hidden="true">
            <span>Branches</span><i /><span>Head office</span>
          </div>
        </div>
        <p className="intro-footer">People. Programmes. Progress.</p>
      </aside>

      <section className="workspace" aria-labelledby="form-title">
        <div className="top-note"><span className="dot" /> Staff portal <span className="demo-badge">DEMO</span></div>
        <div className="card">
          {user ? (
            <div className="welcome" role="status">
              <div className="success-icon" aria-hidden="true">✓</div>
              <p className="eyebrow">YOU'RE SIGNED IN</p>
              <h2 id="form-title">Welcome, {user.name}.</h2>
              <p className="description">Your demo login was successful.</p>
              <dl className="profile">
                <div><dt>Email</dt><dd>{user.email}</dd></div>
                <div><dt>Role</dt><dd>{user.role}</dd></div>
              </dl>
              <p className="demo-note">This is a login prototype. Role dashboards and permission checks will be added next. Refreshing the page ends this demo session.</p>
              <button className="primary" onClick={signOut}>Sign out</button>
            </div>
          ) : (
            <>
              <p className="eyebrow">WELCOME BACK</p>
              <h2 id="form-title">Sign in to your workspace</h2>
              <p className="description">Enter your staff email and password to continue.</p>

              <form onSubmit={signIn} aria-busy={busy}>
                <label htmlFor="email">Email address</label>
                <input id="email" type="email" autoComplete="username" placeholder="you@example.test" value={email} onChange={e => setEmail(e.target.value)} required maxLength={254} disabled={busy} />
                <label htmlFor="password">Password</label>
                <div className="password-field">
                  <input id="password" type={showPassword ? 'text' : 'password'} autoComplete="current-password" placeholder="Enter your password" value={password} onChange={e => setPassword(e.target.value)} required maxLength={128} disabled={busy} />
                  <button type="button" className="show-password" onClick={() => setShowPassword(!showPassword)} aria-label={showPassword ? 'Hide password' : 'Show password'} aria-pressed={showPassword}>{showPassword ? 'Hide' : 'Show'}</button>
                </div>
                {error && <p className="error" role="alert">{error}</p>}
                <button className="primary" type="submit" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'} <span aria-hidden="true">→</span></button>
              </form>

              <details className="demo-accounts">
                <summary>Try a demo account</summary>
                <p>Choose a role to fill the form. All use <code>Demo123!</code>.</p>
                <div className="account-list">
                  {accounts.map(([role, address]) => <button key={address} type="button" disabled={busy} onClick={() => { setEmail(address); setPassword('Demo123!'); setError(''); }}><span>{role}</span><small>{address}</small></button>)}
                </div>
              </details>
              <p className="demo-note">Demo only · Uses sample accounts without a database or persistent authentication.</p>
            </>
          )}
        </div>
        <footer>Branch-to-Head-Office Management Platform</footer>
      </section>
    </main>
  );
}

createRoot(document.getElementById('root')!).render(<StrictMode><App /></StrictMode>);
