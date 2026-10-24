import { useEffect } from 'react';
import App from './App';
import PublicSite from './public/PublicSite';
import { publicPageForPath } from './public/routes';

export default function Site({ path = window.location.pathname }: { path?: string }) {
  const staff = ['/staff','/staff/','/staff/branches','/staff/branches/'].includes(path);
  const page = publicPageForPath(path);
  useEffect(() => {
    if (page) return;
    document.documentElement.lang = 'en';
    document.documentElement.dir = 'ltr';
    document.title = staff ? 'Staff portal | Branch Office' : 'Page not found | Branch Office';
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content', '#500f1c');
  }, [path, staff, page]);

  if (page) return <PublicSite page={page} />;
  if (staff) return <App initialPage={path.startsWith('/staff/branches')?'branches':'home'} />;
  return <main className="public-site public-not-found">
    <h1>Page not found</h1>
    <p>This page isn’t available. You can return to the public website or open the staff portal.</p>
    <a className="home-button" href="/">Go home</a>
    <a href="/staff">Staff sign-in</a>
  </main>;
}
