import { useEffect } from 'react';
import App from './App';
import PublicSite from './public/PublicSite';
import { publicPageForPath } from './public/routes';

export default function Site({ path = window.location.pathname }: { path?: string }) {
  const staff = path === '/staff' || path === '/staff/';
  const page = publicPageForPath(path);
  useEffect(() => {
    if (page) return;
    document.documentElement.lang = 'en';
    document.documentElement.dir = 'ltr';
    document.title = staff ? 'Staff portal | Branch Office' : 'Page not found | Branch Office';
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content', staff ? '#153c35' : '#500f1c');
  }, [path, staff, page]);

  if (page) return <PublicSite page={page} />;
  if (staff) return <App />;
  return <main className="public-site public-not-found">
    <h1>Page not found</h1>
    <p>This page isn’t available. You can return to the public website or open the staff portal.</p>
    <a className="home-button" href="/">Go home</a>
    <a href="/staff">Staff sign-in</a>
  </main>;
}
