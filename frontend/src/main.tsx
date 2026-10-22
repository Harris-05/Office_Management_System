import { StrictMode, useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';

type User = { name: string; email: string; role: string };
type LoginError = { title: string; message: string };

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
  const [error, setError] = useState<LoginError | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const requestInFlight = useRef(false);
  const feedbackRef = useRef<HTMLDivElement>(null);
  const welcomeRef = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    if (error) feedbackRef.current?.focus();
    if (user) welcomeRef.current?.focus();
  }, [error, user]);

  async function signIn(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (requestInFlight.current) return;
    requestInFlight.current = true;
    setError(null);
    setBusy(true);
    try {
      const response = await fetch('/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
        signal: AbortSignal.timeout(10000),
      });
      if (response.status === 401) {
        setError({ title: 'Sign-in unsuccessful', message: 'The email or password is incorrect. Check your details and try again.' });
        return;
      }
      if (!response.ok) {
        setError({ title: 'Sign-in is unavailable', message: 'We could not complete your request. Please try again in a moment.' });
        return;
      }
      const profile: User = await response.json();
      setUser(profile);
      setPassword('');
    } catch (cause) {
      const timedOut = cause instanceof Error && cause.name === 'TimeoutError';
      setError(timedOut
        ? { title: 'Taking longer than expected', message: 'Your request timed out. Please try signing in again.' }
        : { title: 'Unable to connect', message: 'We could not reach the sign-in service. Check your connection and try again.' });
    } finally {
      requestInFlight.current = false;
      setBusy(false);
    }
  }

  function signOut() {
    setUser(null);
    setPassword('');
    setError(null);
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
            <div className="welcome">
              <div className="success-banner" role="status">
                <span className="success-icon" aria-hidden="true">✓</span>
                <div><strong>Signed in successfully</strong><p>Your workspace is ready.</p></div>
              </div>
              <p className="eyebrow">YOU'RE SIGNED IN</p>
              <h2 id="form-title" ref={welcomeRef} tabIndex={-1}>Welcome, {user.name}.</h2>
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
                <input id="email" type="email" autoComplete="username" placeholder="you@example.test" value={email} onChange={e => { setEmail(e.target.value); setError(null); }} required maxLength={254} disabled={busy} aria-describedby={error ? 'login-error' : undefined} />
                <label htmlFor="password">Password</label>
                <div className="password-field">
                  <input id="password" type={showPassword ? 'text' : 'password'} autoComplete="current-password" placeholder="Enter your password" value={password} onChange={e => { setPassword(e.target.value); setError(null); }} required maxLength={128} disabled={busy} aria-describedby={error ? 'login-error' : undefined} />
                  <button type="button" className="show-password" disabled={busy} onClick={() => setShowPassword(!showPassword)} aria-label={showPassword ? 'Hide password' : 'Show password'} aria-pressed={showPassword}>{showPassword ? 'Hide' : 'Show'}</button>
                </div>
                {error && <div id="login-error" className="feedback-error" role="alert" ref={feedbackRef} tabIndex={-1}>
                  <span className="error-icon" aria-hidden="true">!</span>
                  <div><strong>{error.title}</strong><p>{error.message}</p></div>
                </div>}
                <button className={`primary${busy ? ' is-loading' : ''}`} type="submit" disabled={busy} aria-busy={busy}>
                  {busy ? <><span className="spinner" aria-hidden="true" /> Signing in…</> : <>Sign in <span aria-hidden="true">→</span></>}
                </button>
                <p className="request-status" role="status" aria-live="polite">{busy ? 'Checking your details. Please wait…' : ''}</p>
              </form>

              <details className="demo-accounts">
                <summary>Try a demo account</summary>
                <p>Choose a role to fill the form. All use <code>Demo123!</code>.</p>
                <div className="account-list">
                  {accounts.map(([role, address]) => <button key={address} type="button" disabled={busy} onClick={() => { setEmail(address); setPassword('Demo123!'); setError(null); }}><span>{role}</span><small>{address}</small></button>)}
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
