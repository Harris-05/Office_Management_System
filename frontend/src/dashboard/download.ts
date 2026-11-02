import {ApiError} from '../api';

/** Keep the authenticated response and honest error in the current staff session. */
export async function downloadCollections(query: string): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`/api/dashboard/export.csv${query ? `?${query}` : ''}`, {
      credentials: 'same-origin', signal: AbortSignal.timeout(30000),
    });
  } catch {
    throw new Error('Unable to download. Check your connection and try again.');
  }
  if (!response.ok) {
    if (response.status === 401) window.dispatchEvent(new Event('branch-session-invalid'));
    const body = await response.json().catch(() => undefined);
    throw new ApiError(response.status, typeof body?.detail === 'string' ? body.detail : 'Unable to export collections. Please try again.');
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = 'collections.csv';
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  // Give the browser time to start reading the object URL before releasing it.
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}
