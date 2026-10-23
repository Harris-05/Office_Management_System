import { useEffect, useRef } from 'react';

export function Feedback({ error, success }: { error?: string; success?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => { if (error) ref.current?.focus(); }, [error]);
  if (error) return <div className="feedback-error" role="alert" tabIndex={-1} ref={ref}><div><strong>Unable to complete this action</strong><p>{error}</p></div></div>;
  if (success) return <div className="success-banner" role="status"><div><strong>{success}</strong></div></div>;
  return null;
}

export function Submit({ busy, idle, pending }: { busy: boolean; idle: string; pending: string }) {
  return <button type="submit" className={`primary${busy ? ' is-loading' : ''}`} disabled={busy} aria-busy={busy}>
    {busy && <span className="spinner" aria-hidden="true" />}{busy ? pending : idle}
  </button>;
}

export function passwordError(value: string): string | null {
  return value.length < 15 || new TextEncoder().encode(value).length > 72 || value.includes('\0')
    ? 'Use at least 15 characters and no more than 72 UTF-8 bytes. Spaces are welcome.' : null;
}
